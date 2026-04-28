from airflow.plugins_manager import AirflowPlugin

import prometheus_task_listener


class PrometheusTaskListenerPlugin(AirflowPlugin):
    name = "prometheus_task_listener"
    listeners = [prometheus_task_listener]
