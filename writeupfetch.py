import trafilatura

url = "https://medium.com/@EtcSec/picoctf-vault-door-3-490412e09e22"
downloaded = trafilatura.fetch_url(url)
text = trafilatura.extract(downloaded)

print(text)