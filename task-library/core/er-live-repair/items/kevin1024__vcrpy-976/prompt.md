## Issue (kevin1024/vcrpy)

AttributeError: 'VCRHTTPResponse' object has no attribute 'url'

Hi,

I'm using VCR.py for testing some code using Dulwich which in turn uses urllib3 under the hood.

Recently Dulwich updated their urllib3 dependency to some version >=2.2 and changed some code which relies on `geturl` existing on `HTTPResponse`: https://github.com/jelmer/dulwich/commit/dca4d6ded4db15caf8e06a2f101be71b6528f5b0#diff-4892c787e6ba376b2ad0d9e24b3c7d6398b8ec53112c369df2ab664d921adb25R4600, which seems to be a fair assumption: https://github.com/urllib3/urllib3/blob/2.0.x/src/urllib3/response.py#L500.

Unfortunately, I noticed in [one of my dependency update MRs](https://gitlab.com/dAnjou/fs-code/-/merge_requests/142) which brings the above changes that now my tests are failing with the following error: 
```
Traceback (most recent call last):
  File "/builds/dAnjou/fs-code/src/codefs/_core.py", line 107, in _delegate
    self.mount(mount_point, self.fetch_archive(ref))
  File "/builds/dAnjou/fs-code/src/codefs/gitfs/__init__.py", line 84, in __call__
    repo = self._client.clone(
  File "/usr/local/lib/python3.10/site-packages/dulwich/client.py", line 1155, in clone
    result = self.fetch(
  File "/usr/local/lib/python3.10/site-packages/dulwich/client.py", line 1285, in fetch
    result = self.fetch_pack(
  File "/usr/local/lib/python3.10/site-packages/dulwich/client.py", line 4204, in fetch_pack
    refs, server_capabilities, url, symrefs, _peeled = self._discover_references(
  File "/usr/local/lib/python3.10/site-packages/dulwich/client.py", line 3923, in _discover_references
    resp, read = self._http_request(url, headers)
  File "/usr/local/lib/python3.10/site-packages/dulwich/client.py", line 4605, in _http_request
    resp_url = resp.geturl()
  File "/usr/local/lib/python3.10/http/client.py", line 781, in geturl
    return self.url
AttributeError: 'VCRHTTPResponse' object has no attribute 'url'
```
Full CI job logs: https://gitlab.com/dAnjou/fs-code/-/jobs/12819211460#L1071

This seems to be a rather trivial fix, so if you could give me a hint where to add this, I'm inclined to follow up with a PR 🙂 

My guess would be https://github.com/kevin1024/vcrpy/blob/master/vcr/stubs/urllib3_stubs.py but I'm not totally sure.

Thanks! 🙏

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
