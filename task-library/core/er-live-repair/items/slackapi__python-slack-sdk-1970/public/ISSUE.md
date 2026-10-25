Token rotation failed to refresh the token in a certain time period when using SQLAlchemyInstallationStore

I encountered an issue when the access token was expired, and the function [perform_bot_token_rotation](https://github.com/slackapi/python-slack-sdk/blob/7e3ab80cdfc4c257c2b46b630546d38920502064/slack_sdk/oauth/token_rotation/rotator.py#L76) failed to refresh the token, it return None because the condition is not satisfied.

I think the root cause is that when we save the installation instance, the SDK calls [datetime.utcfromtimestamp()](https://github.com/slackapi/python-slack-sdk/blob/7e3ab80cdfc4c257c2b46b630546d38920502064/slack_sdk/oauth/installation_store/models/installation.py#L176) to convert the timestamp into a naive datetime object (which doesn’t have timezone information). Later, when the SDK tries to find the installation, the SDK calls [datetime.timestamp()](https://github.com/slackapi/python-slack-sdk/blob/7e3ab80cdfc4c257c2b46b630546d38920502064/slack_sdk/oauth/installation_store/internals.py#L38) on this naive datetime object to get the timestamp value, it assumes the value is in local time, so the resulting timestamp includes the time zone offset.

For example, my app is installed on 2025-08-23 00:00:00 (UTC), the access token should be expired on 2025-08-23 12:00:00 (UTC).
The installation store save the naive datetime object of 2025-08-23 12:00:00 (No timezone info) for `bot_token_expires_at` to database.
When the SDK calls `find_installation` function, it will convert the naive datetime 2025-08-23 12:00:00 (No timezone info) to a timestamp represent the datetime 2025-08-23 19:00:00 (UTC) because I am in UTC-7 timezone.
At the time 2025-08-23 12:00:00 (UTC), the bot token is expired on Slack backend, but when the SDK calls the function [perform_bot_token_rotation](https://github.com/slackapi/python-slack-sdk/blob/7e3ab80cdfc4c257c2b46b630546d38920502064/slack_sdk/oauth/token_rotation/rotator.py#L75), the `bot_token_expires_at` is 2025-08-23 19:00:00 (UTC) and `time() + minutes_before_expiration * 60` is 2025-08-23 14:00:00 (UTC), which will not refresh the token.

### Reproducible in:

```bash
pip freeze | grep slack
python --version
sw_vers && uname -v # or `ver`
```

#### The `slack_bolt` version

slack-bolt==1.23.0
slack-sdk==3.36.0

#### Python runtime version

python 3.13.6

#### OS info

Any

#### Steps to reproduce:

(Share the commands to run, source code, and project settings (e.g., setup.py))

1. enable token rotation
2. use SQLAlchemyInstallationStore as installation_store
3. the token will not be refreshed in a certain time period (the time period depend on your local time zone)

### Expected result:

The token should be refreshed when the token is about to expire.

### Actual result:

The access token is expired, but when execute the function [perform_bot_token_rotation](https://github.com/slackapi/python-slack-sdk/blob/7e3ab80cdfc4c257c2b46b630546d38920502064/slack_sdk/oauth/token_rotation/rotator.py#L76), it return None because the condition is not satisfied.

Can't tell much about the issue from the log, but still attached below:
```
DEBUG:main:Applying slack_bolt.middleware.ssl_check.ssl_check.SslCheck
DEBUG:main:Applying slack_bolt.middleware.request_verification.request_verification.RequestVerification
DEBUG:main:Applying slack_bolt.middleware.authorization.multi_teams_authorization.MultiTeamsAuthorization
INFO:sqlalchemy.engine.Engine:BEGIN (implicit)
INFO:sqlalchemy.engine.Engine:SELECT slack_installations.id, slack_installations.client_id, slack_installations.app_id, slack_installations.enterprise_id, slack_installations.enterprise_name, slack_installations.enterprise_url, slack_installations.team_id, slack_installations.team_name, slack_installations.bot_token, slack_installations.bot_id, slack_installations.bot_user_id, slack_installations.bot_scopes, slack_installations.bot_refresh_token, slack_installations.bot_token_expires_at, slack_installations.user_id, slack_installations.user_token, slack_installations.user_scopes, slack_installations.user_refresh_token, slack_installations.user_token_expires_at, slack_installations.incoming_webhook_url, slack_installations.incoming_webhook_channel, slack_installations.incoming_webhook_channel_id, slack_installations.incoming_webhook_configuration_url, slack_installations.is_enterprise_install, slack_installations.token_type, slack_installations.installed_at 
FROM slack_installations 
WHERE slack_installations.client_id = ? AND slack_installations.enterprise_id IS NULL AND slack_installations.team_id = ? ORDER BY slack_installations.installed_at DESC
 LIMIT ? OFFSET ?
INFO:sqlalchemy.engine.Engine:[cached since 139.8s ago] ('9384663881440.9365392779238', 'T09BAKHRXCY', 1, 0)
INFO:sqlalchemy.engine.Engine:ROLLBACK
DEBUG:main:Sending a request - url: https://slack.com/api/auth.test, query_params: {}, body_params: {'team_id': 'T09BAKHRXCY'}, files: {}, json_body: None, headers: {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': '(redacted)', 'User-Agent': 'Python/3.13.6 slackclient/3.36.0 Darwin/24.5.0'}
DEBUG:main:Received the following response - status: 200, headers: {'date': 'Sat, 23 Aug 2025 17:12:08 GMT', 'server': 'Apache', 'vary': 'Accept-Encoding', 'x-slack-req-id': '0efda839951239c4b94e54160d5f95f8', 'x-content-type-options': 'nosniff', 'x-xss-protection': '0', 'x-robots-tag': 'noindex,nofollow', 'pragma': 'no-cache', 'cache-control': 'private, no-cache, no-store, must-revalidate', 'expires': 'Sat, 26 Jul 1997 05:00:00 GMT', 'content-type': 'application/json; charset=utf-8', 'x-slack-failure': 'token_expired', 'access-control-expose-headers': 'x-slack-req-id, retry-after', 'access-control-allow-headers': 'slack-route, x-slack-version-ts, x-b3-traceid, x-b3-spanid, x-b3-parentspanid, x-b3-sampled, x-b3-flags', 'strict-transport-security': 'max-age=31536000; includeSubDomains; preload', 'referrer-policy': 'no-referrer', 'x-slack-unique-id': 'aKn2aIkSO2ZNzfyKteK29gAAACw', 'x-slack-backend': 'r', 'access-control-allow-origin': '*', 'content-length': '36', 'via': '1.1 slack-prod.tinyspeck.com, envoy-www-iad-zddpmfxg,envoy-edge-pdx-xxczocxg', 'x-envoy-attempt-count': '1', 'x-envoy-upstream-service-time': '73', 'x-backend': 'main_normal main_canary_with_overflow main_control_with_overflow', 'x-server': 'slack-www-hhvm-main-iad-lxip', 'x-slack-shared-secret-outcome': 'no-match', 'x-edge-backend': 'envoy-www', 'timing-allow-origin': '*', 'x-slack-edge-shared-secret-outcome': 'no-match', 'connection': 'close'}, body: {"ok":false,"error":"token_expired"}
DEBUG:main:The stored bot token for enterprise_id: None team_id: T09BAKHRXCY is no longer valid. (response: {'ok': False, 'error': 'token_expired'})
ERROR:slack_bolt.MultiTeamsAuthorization:Although the app should be installed into this workspace, the AuthorizeResult (returned value from authorize) for it was not found.
```

### Requirements

For general questions/issues about Slack API platform or its server-side, could you submit questions at https://my.slack.com/help/requests/new instead. :bow:

Please read the [Contributing guidelines](https://github.com/slackapi/python-slack-sdk/blob/main/.github/contributing.md) and [Code of Conduct](https://slackhq.github.io/code-of-conduct) before creating this issue or pull request. By submitting, you are agreeing to those rules.
