import instaloader
import logging
import json

class ResumableNodeIterator:
    """
    A custom wrapper around Instaloader's NodeIterator that supports
    account-agnostic resuming via an end_cursor.
    """
    def __init__(self, node_iterator, neo4j_manager, profile_id, scraper_username, data_type, total_count):
        self.node_iterator = node_iterator
        self.neo4j_manager = neo4j_manager
        self.profile_id = profile_id
        self.scraper_username = scraper_username # For saving the hash if we get interrupted
        self.data_type = data_type
        self.total = total_count
        self.is_resumed = False
        self.logger = logging.getLogger(__name__)
        self._init_resume_state()

    def _init_resume_state(self):
        """Initializes the iterator to a saved resume point if one exists."""
        resume_data = self.neo4j_manager.execute_read(
            self.neo4j_manager.get_shared_resume_cursor,
            self.profile_id,
            self.data_type
        )
        if resume_data and resume_data.get("end_cursor"):
            try:
                self.logger.info(f"♻  Found shared resume point. Resuming {self.data_type} fetch...")
                # This is the key part: we are modifying the iterator's internal state
                # to start from the shared cursor.
                # We must set it this way as the attribute may not exist yet.
                setattr(self.node_iterator, 'page_info', {
                    'end_cursor': resume_data["end_cursor"], 'has_next_page': True
                })
                self.node_iterator.nodes_per_chunk = 50 # Standard page size
                self.node_iterator._total_index = resume_data.get("count", 0)

                self.is_resumed = True
            except Exception as e:
                self.logger.warning(f"Failed to resume from shared cursor: {e}. Starting from scratch.")

    def __iter__(self):
        return self

    def __next__(self):
        """
        Yields the next item from the underlying iterator and saves the
        pagination state (end_cursor) after each page fetch.
        """
        # The `_yield_value` method in instaloader's NodeIterator is a generator.
        # When it fetches a new page of results, it updates its `page_info`.
        # We can hook into this to save our state.

        # Store the cursor *before* getting the next item, in case it fails.
        page_info = getattr(self.node_iterator, 'page_info', {})
        current_cursor = page_info.get('end_cursor') if page_info else None
        current_count = getattr(self.node_iterator, 'total_index', 0)

        try:
            item = next(self.node_iterator)
            new_cursor = getattr(self.node_iterator, 'page_info', {}).get('end_cursor')

            # If the cursor has changed, it means a new page was fetched.
            if new_cursor != current_cursor:
                self.save_resume_state(new_cursor, getattr(self.node_iterator, 'total_index', 0))

            return item
        except StopIteration:
            # The iteration is complete, clear the resume state.
            self.clear_resume_state()
            raise
        except Exception as e:
            # On any other error (e.g., rate limit), save the *current* state
            # so another account can pick it up.
            self.save_resume_state(current_cursor, current_count)
            self.logger.warning(f"Error during iteration. Saved shared resume point at cursor: {current_cursor}")
            raise

    def save_resume_state(self, end_cursor, count):
        """Saves the shared end_cursor to Neo4j."""
        if end_cursor:
            self.neo4j_manager.execute_write(
                self.neo4j_manager.save_shared_resume_cursor,
                self.profile_id,
                self.data_type,
                end_cursor,
                count
            )

    def clear_resume_state(self):
        """Clears the shared resume state upon successful completion."""
        self.neo4j_manager.execute_write(
            self.neo4j_manager.clear_shared_resume_cursor,
            self.profile_id,
            self.data_type
        )

    def freeze(self):
        """
        Provides a fallback to instaloader's native freeze for partial saves within a single account's run.
        """
        return self.node_iterator.freeze()