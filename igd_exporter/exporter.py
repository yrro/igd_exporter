import cgi
import html
import socket
import urllib
import wsgiref.util

import prometheus_client

from . import igd

def wsgi_app(environ, start_response):
    '''
    Base WSGI application that routes requests to other applications.
    '''
    name = wsgiref.util.shift_path_info(environ)
    if name == '':
        return front(environ, start_response)
    if name == 'probe':
        return probe(environ, start_response)
    elif name == 'metrics':
        return prometheus_app(environ, start_response)
    return not_found(environ, start_response)

def front(environ, start_response):
    '''
    Front page, containing links to the expoter's own metrics, as well as links
    to probe discovered devices.
    '''
    global targets

    if environ['REQUEST_METHOD'] == 'POST':
        form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ, strict_parsing=1, encoding='latin1')
        if form.getfirst('search') == '1':
            targets = list(igd.search(5))

    config = []
    if targets:
        config.append(
            b'<p>Example config for the above devices:'
            b'<pre>\n'
            b'scrape_configs:\n'
            b'  - job_name: igd\n'
            b'    metrics_path: /probe\n'
            b'    static_configs:\n'
            b'      - targets:\n'
        )
        config.append(
            *[b'          - %b\n' % html.escape(t).encode('latin1') for t in targets]
        )
        config.append(
            b'    relabel_configs:\n'
            b'      - source_labels: [__address__]\n'
            b'        target_label: __param_target\n'
            b'      - source_labels: [__param_target]\n'
            b'        target_label: instance\n'
            b'      - target_label: __address__\n'
            b'        replacement: %b # IGD exporter\n' % html.escape(environ['HTTP_HOST']).encode('latin1')
        )
        config.append(
            b'</pre>'
        )

    start_response('200 OK', [('Content-Type', 'text/html')])
    return [
        b'<html>'
            b'<head><title>WSG exporter</title></head>'
            b'<body>'
                b'<h1>IGD Exporter</h1>'
                b'<form method="post"><p><input type="hidden" name="search" value="1"><button type="submit">Search</button> for devices on local network (5 second timeout)</input></form>',
                *[b'<p><a href="/probe?target=%b">Probe %b</a>' % (html.escape(urllib.parse.quote_plus(t)).encode('latin1'), html.escape(t).encode('latin1')) for t in targets],
                b'<p><a href="/metrics">Metrics</a>',
                *config,
            b'</body>'
        b'</html>'
    ]

# Discovered devices are kept in this list.
targets = []

def probe(environ, start_response):
    '''
    Performs a probe using the given root device URL.
    '''
    qs = urllib.parse.parse_qs(environ['QUERY_STRING'])
    body = igd.probe(qs['target'][0])
    start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8; version=0.0.4')])
    return body

prometheus_app = prometheus_client.make_wsgi_app()

def not_found(environ, start_response):
    '''
    How did we get here?
    '''
    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b'Not Found\r\n']
