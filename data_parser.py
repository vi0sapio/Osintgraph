
## Extract target user data
def extract_profile_data(profile):
    """
    General function to extract profile data from a profile.
    Can be used for followers, followees, or single user profiles.
    """
    return {
        'username': getattr(profile, 'username', None),
        'id': getattr(profile, 'userid', None),
        'fullname': getattr(profile, 'full_name', None),
        'bio': getattr(profile, 'biography', None),
        'biography_mentions': getattr(profile, 'biography_mentions', None),
        'biography_hashtags': getattr(profile, 'biography_hashtags', None),
        'blocked_by_viewer': getattr(profile, 'blocked_by_viewer', None),
        'business_category_name': getattr(profile, 'business_category_name', None),
        'external_url': getattr(profile, 'external_url', None),
        'followed_by_viewer': getattr(profile, 'followed_by_viewer', None),
        'followees': getattr(profile, 'followees', None),
        'followers': getattr(profile, 'followers', None),
        'follows_viewer': getattr(profile, 'follows_viewer', None),
        'has_blocked_viewer': getattr(profile, 'has_blocked_viewer', None),
        'has_highlight_reels': getattr(profile, 'has_highlight_reels', None),
        'has_public_story': getattr(profile, 'has_public_story', None),
        'is_business_account': getattr(profile, 'is_business_account', None),
        'is_private': getattr(profile, 'is_private', None),
        'is_verified': getattr(profile, 'is_verified', None),
        'profile_pic_url': getattr(profile, 'profile_pic_url', None),
        'profile_pic_url_no_iphone': getattr(profile, 'profile_pic_url_no_iphone', None),
        'mediacount': getattr(profile, 'mediacount', None),
        # 'igtvcount': getattr(profile, 'igtvcount', None),
        'has_requested_viewer': getattr(profile, 'has_requested_viewer', None),
    }

## Extract follower/followee data
def map_data(person):
    """
    Maps the follower object to a dictionary containing relevant data.
    """
    return {
        'id': int(person._node['id']),
        'username': person._node['username'],
        'full_name': person._node['full_name'],
        'profile_pic_url': person._node['profile_pic_url'],
        'is_verified': person._node['is_verified'],
        '_has_full_metadata': person._has_full_metadata,
        '_has_public_story': person._has_public_story
    }