#!/usr/bin/env python

import commands
import json
import datetime
import sys
sys.path.insert(0, r'./python-texttable/')

from texttable import Texttable, get_color_string, bcolors

# import pprint
# pp = pprint.PrettyPrinter(indent=2)
# pp.pprint()

namespace = "kube-system"
nodes_dict = {}
pods = []
svcs = []

def format_duration(seconds):
  res = ""
  if seconds > 60 * 60 * 24:
    res = "%d%s" % (int(seconds / (60 * 60 * 24)), "d")
  elif seconds > 60 * 60:
    res = "%d%s" % (int(seconds / (60 * 60)), "h")
  elif seconds > 60:
    res = "%d%s" % (int(seconds / 60), "m")
  else:
    res = "%d%s" % (int(seconds), "s")
  return res

def get_pod_age(startTime):
  date = datetime.datetime.strptime(startTime, "%Y-%m-%dT%H:%M:%SZ")
  seconds = (datetime.datetime.now() - date).total_seconds()
  return format_duration(seconds)

def get_nodes():
  nodes_cmd = "kubectl --namespace %s get nodes -o json" % namespace
  nodes_json = commands.getoutput(nodes_cmd)
  nodes = json.loads(nodes_json)["items"]

  for node in nodes:
    node_name = node["metadata"]["name"]
    os_image = node["status"]["nodeInfo"]["osImage"]

    status = "Ready"
    for condition in node["status"]["conditions"]:
      if condition["type"] == "Ready":
        if condition["status"] != "True":
          status = "NotReady"

    role = "worker"
    if node["metadata"]["labels"].has_key("node-role.kubernetes.io/master"):
      role = "master"

    unschedulable = False
    if node["spec"].has_key("unschedulable") and node["spec"]["unschedulable"] == True:
      unschedulable = True

    nodes_dict[node_name] = {
      "name": node_name,
      "osImage": os_image,
      "role": role,
      "status": status,
      "unschedulable": unschedulable,
      "pods": []
    }
  return

def get_pods():
  pods_cmd = "kubectl --namespace %s get pods -o json" % namespace
  pods_json = commands.getoutput(pods_cmd)
  pods.extend(json.loads(pods_json)["items"])

def get_svcs():
  svcs_cmd = "kubectl --namespace %s get svc -o json" % namespace
  svcs_json = commands.getoutput(svcs_cmd)
  svcs.extend(json.loads(svcs_json)["items"])

def get_pod_port(pod_label):
  port = ""
  target_port = ""
  port_list = []
  target_port_list = []
  for svc in svcs:
    if svc["spec"].has_key("selector") and svc["spec"]["selector"].has_key("name") and svc["spec"]["selector"]["name"] == pod_label:
      for port in svc["spec"]["ports"]:
        port_list.append("%s/%s" % (port["port"], port["protocol"]))
        target_port_list.append("%s/%s" % (port["targetPort"], port["protocol"]))
      port = ",".join(port_list)
      target_port = ",".join(target_port_list)

  return {
    "port": port,
    "target_port": target_port
  }

def sort_node_pods():
  for pod in pods:
    pod_name = pod["metadata"]["name"]
    pod_status = pod["status"]["phase"]
    node_name = pod["spec"]["nodeName"]
    restart_count = 0
    for cs in pod["status"]["containerStatuses"]:
      restart_count = restart_count + cs["restartCount"]
    start_time = pod['status']['startTime']
    pod_label = ""
    if pod["metadata"]["labels"].has_key("name"):
      pod_label = pod["metadata"]["labels"]["name"]
    ports = get_pod_port(pod_label)
    if nodes_dict.has_key(node_name):
      nodes_dict[node_name]["pods"].append({
        "name": pod_name,
        "status": pod_status,
        "restart_count": restart_count,
        "age": get_pod_age(start_time),
        "port": ports["port"],
        "target_port": ports["target_port"]
      })

def print_nodes():
  node_table = Texttable()
  node_table.set_deco(Texttable.HEADER)
  node_table.set_cols_align(["l", "l", "l", "l"])
  node_rows = [["NAME", "ROLE", "STATUS", "OS"]]

  for node_name in nodes_dict.keys():
    node = nodes_dict[node_name]
    status = ""
    if node["status"] == "Ready":
      status = get_color_string(bcolors.GREEN, node["status"])
    else:
      status = get_color_string(bcolors.RED, node["status"])
    if node["unschedulable"]:
      status = "%s,%s" % (status, get_color_string(bcolors.YELLOW, "SchedulingDisabled"))
    node_rows.append([node["name"], node["role"], status, node["osImage"]])

  node_table.add_rows(node_rows)
  print node_table.draw() + "\n\n"

def print_node_pods():
  for node_name in nodes_dict.keys():
    node = nodes_dict[node_name]
    pods_table = Texttable(0)
    pods_table.set_deco(Texttable.HEADER)
    pods_table.set_cols_align(["l", "r", "r", "r", "r", "r"])
    pods_rows = [["NAME", "STATUS", "RESTART", "AGE", "TARGET PORT", "PORT"]]

    if len(node["pods"]) > 0:
      for pod in node["pods"]:
        status = ""
        if pod["status"] == "Running":
          status = get_color_string(bcolors.GREEN, pod["status"])
        else:
          status = get_color_string(bcolors.YELLOW, pod["status"])
        pods_rows.append([pod["name"], status, pod["restart_count"], pod["age"], pod["target_port"], pod["port"]])
      pods_table.add_rows(pods_rows)
      print node_name
      print pods_table.draw() + "\n\n"

get_nodes()
get_pods()
get_svcs()
sort_node_pods()
print_nodes()
print_node_pods()
