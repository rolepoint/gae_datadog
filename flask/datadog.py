# stdlib
from collections import defaultdict
from datetime import datetime, timedelta
import os
import time

# google api
from google.appengine.api import app_identity, logservice, memcache, taskqueue
from google.appengine.ext.db import stats as db_stats

# flask
from flask import Flask, abort, jsonify, request
app = Flask(__name__)


@app.route('/datadog')
def datadog_stats():
    auth_token = request.args.get('auth_token')
    if auth_token != os.environ('DATADOG_AUTH_TOKEN'):
        abort(403)

    FLAVORS = ['requests', 'services', 'all']

    flavor = request.args.get('flavor')
    if flavor not in FLAVORS:
        abort(400)

    def get_task_queue_stats(queues=None):
        if queues is None:
            queues = ['default']
        else:
            queues = queues.split(',')
        task_queues = [taskqueue.Queue(q).fetch_statistics() for q in queues]
        q_stats = []
        for q in task_queues:
            stats = {
                'queue_name': q.queue.name,
                'tasks': q.tasks,
                'oldest_eta_usec': q.oldest_eta_usec,
                'executed_last_minute': q.executed_last_minute,
                'in_flight': q.in_flight,
                'enforced_rate': q.enforced_rate,
            }
            q_stats.append(stats)
        return q_stats
    def get_request_stats(after=None):
        if after is None:
            one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
            after = time.mktime(one_minute_ago.timetuple())
        else:
            # cast to float
            after = float(after)

        logs = logservice.fetch(start_time=after)
        stats = defaultdict(list)
        for req_log in logs:
            stats['start_time'].append(req_log.start_time)
            stats['api_mcycles'].append(req_log.api_mcycles)
            stats['cost'].append(req_log.cost)
            stats['finished'].append(req_log.finished)
            stats['latency'].append(req_log.latency)
            stats['mcycles'].append(req_log.mcycles)
            stats['pending_time'].append(req_log.pending_time)
            stats['replica_index'].append(req_log.replica_index)
            stats['response_size'].append(req_log.response_size)
            stats['version_id'].append(req_log.version_id)
        return stats

    stats = {
        'project_name': app_identity.get_application_id()
    }
    if flavor == 'services' or flavor == 'all':
        stats['datastore'] = db_stats.GlobalStat.all().get()
        stats['memcache'] = memcache.get_stats()
        stats['task_queue'] = get_task_queue_stats(request.args.get('task_queues'))

    if flavor == 'requests' or flavor == 'all':
        stats['requests'] = get_request_stats(request.args.get('after'))

    return jsonify(**stats)

@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, nothing at this URL.', 404