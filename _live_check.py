import re
import urllib.request

url = 'https://osamasla.github.io/Arabic-Bible-documentary/documents/adrien-ladrierre/doc_0005.html'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode('utf-8', 'ignore')
    hrefs = re.findall(r'href="([^"]*css/style\.css)"', body)
    print('status: 200')
    print('live style.css hrefs:', hrefs)
    # resolve against page dir
    import posixpath
    page = '/Arabic-Bible-documentary/documents/adrien-ladrierre/doc_0005.html'
    base = posixpath.dirname(page) + '/'
    for h in hrefs:
        print('resolves to:', posixpath.normpath(base + h))
except Exception as e:
    print('FETCH ERR:', e)
