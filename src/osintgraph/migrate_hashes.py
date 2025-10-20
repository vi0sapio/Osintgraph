import logging
import json

from .neo4j_manager import Neo4jManager

def migrate_resume_hashes(neo4j_manager: Neo4jManager):
    """
    One-time migration to convert old session-specific resume hashes 
    to the new shared end_cursor format.
    """
    logger = logging.getLogger(__name__)
    logger.info("Checking for old resume hashes to migrate...")

    migrated_count_total = 0
    
    while True:
        nodes_to_migrate = []
        with neo4j_manager.get_session() as session:
            # Step 1: Fetch nodes with old hashes
            fetch_query = """
                MATCH (p:Person)
                WHERE (p._followers_resume_hash IS NOT NULL AND p._followers_resume_hash <> "")
                   OR (p._followees_resume_hash IS NOT NULL AND p._followees_resume_hash <> "")
                   OR (p._posts_resume_hash IS NOT NULL AND p._posts_resume_hash <> "")
                RETURN p.id as id, p._followers_resume_hash as followers, p._followees_resume_hash as followees, p._posts_resume_hash as posts
                LIMIT 500
            """
            results = session.run(fetch_query)
            nodes_to_migrate = [record.data() for record in results]

        if not nodes_to_migrate:
            break # No more nodes to migrate

        # Step 2: Process and update nodes in a separate transaction
        updates = []
        for node in nodes_to_migrate:
            update_payload = {'id': node['id']}
            for data_type in ['followers', 'followees', 'posts']:
                hash_str = node.get(data_type)
                if hash_str:
                    try:
                        hash_data = json.loads(hash_str)
                        # Correctly parse the nested structure of the old hash format
                        end_cursor = hash_data.get('node', {}).get('remaining_data', {}).get('page_info', {}).get('end_cursor') or hash_data.get('remaining_data', {}).get('page_info', {}).get('end_cursor')
                        count = hash_data.get('node', {}).get('total_index') or hash_data.get('remaining_data', {}).get('count')
                        if end_cursor is not None and count is not None:
                            new_cursor_data = json.dumps({'end_cursor': end_cursor, 'count': count})
                            update_payload[data_type] = new_cursor_data
                    except (json.JSONDecodeError, AttributeError, KeyError):
                        logger.warning(f"Could not parse old hash for node {node['id']}, type {data_type}. Skipping.")
            updates.append(update_payload)

        with neo4j_manager.get_session() as session:
            # Step 3: Write the new data and remove old properties
            update_query = """
                UNWIND $updates as update
                MATCH (p:Person {id: update.id})
                // Atomically set new cursor and remove old hash only if new cursor exists
                FOREACH (_ IN CASE WHEN update.followers IS NOT NULL THEN [1] ELSE [] END |
                    SET p._shared_followers_cursor = update.followers
                    REMOVE p._followers_resume_hash
                )
                FOREACH (_ IN CASE WHEN update.followees IS NOT NULL THEN [1] ELSE [] END |
                    SET p._shared_followees_cursor = update.followees
                    REMOVE p._followees_resume_hash
                )
                FOREACH (_ IN CASE WHEN update.posts IS NOT NULL THEN [1] ELSE [] END |
                    SET p._shared_posts_cursor = update.posts
                    REMOVE p._posts_resume_hash
                )
            """
            session.run(update_query, updates=updates)
        
        migrated_count_total += len(nodes_to_migrate)
        logger.info(f"Migrated a batch of {len(nodes_to_migrate)} nodes...")

    if migrated_count_total > 0:
        logger.info(f"✓  Successfully migrated {migrated_count_total} total nodes to the new resume format.")
    else:
        logger.info("✓  No old resume hashes found to migrate.")