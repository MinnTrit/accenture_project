from celery import Celery

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    celery.conf.CELERY_INCLUDE = ['tasks']
    celery.conf.CELERYBEAT_SCHEDULER = 'redbeat.RedBeatScheduler'
    celery.conf.REDBEAT_LOCK_TIMEOUT = 0
    celery.autodiscover_tasks(['tasks'])
    
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery
