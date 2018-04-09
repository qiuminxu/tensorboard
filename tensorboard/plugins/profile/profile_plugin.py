# -*- coding: utf-8 -*-
# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""The TensorBoard plugin for performance profiling."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import os
import tensorflow as tf
from werkzeug import wrappers

from tensorboard.backend import http_util
from tensorboard.backend.event_processing import plugin_asset_util
from tensorboard.plugins import base_plugin
from tensorboard.plugins.profile import trace_events_json
from tensorboard.plugins.profile import trace_events_pb2

# The prefix of routes provided by this plugin.
PLUGIN_NAME = 'profile'

# HTTP routes
LOGDIR_ROUTE = '/logdir'
DATA_ROUTE = '/data'
TOOLS_ROUTE = '/tools'
HOSTS_ROUTE = '/hosts'

# Available profiling tools -> file name of the tool data.
_FILE_NAME = 'TOOL_FILE_NAME'
TOOLS = {
    'trace_viewer': 'trace',
    'op_profile': 'op_profile.json',
    'input_pipeline_analyzer': 'input_pipeline.json',
    'overview_page': 'overview_page.json'
}

# Tools that consume raw data.
_RAW_DATA_TOOLS = frozenset(['input_pipeline_analyzer',
                             'op_profile',
                             'overview_page'])

def process_raw_trace(raw_trace):
  """Processes raw trace data and returns the UI data."""
  trace = trace_events_pb2.Trace()
  trace.ParseFromString(raw_trace)
  return ''.join(trace_events_json.TraceEventsJsonStream(trace))


class ProfilePlugin(base_plugin.TBPlugin):
  """Profile Plugin for TensorBoard."""

  plugin_name = PLUGIN_NAME

  def __init__(self, context):
    """Constructs a profiler plugin for TensorBoard.

    This plugin adds handlers for performance-related frontends.

    Args:
      context: A base_plugin.TBContext instance.
    """
    self.logdir = context.logdir
    self.plugin_logdir = plugin_asset_util.PluginDirectory(
        self.logdir, ProfilePlugin.plugin_name)

  @wrappers.Request.application
  def logdir_route(self, request):
    return http_util.Respond(request, {'logdir': self.plugin_logdir},
                             'application/json')

  def _run_dir(self, run):
    run_dir = os.path.join(self.plugin_logdir, run)
    return run_dir if tf.gfile.IsDirectory(run_dir) else None

  def index_impl(self):
    """Returns available runs and available tool data in the log directory.

    In the plugin log directory, each directory contains profile data for a
    single run (identified by the directory name), and files in the run
    directory contains data for different tools. The file that contains profile
    for a specific tool "x" will have a suffix name TOOLS["x"].
    Example:
      log/
        run1/
          plugins/
            profile/
              host1.trace
              host2.trace
        run2/
          plugins/
            profile/
              host1.trace
              host2.trace

    Returns:
      A map from runs to tool names e.g.
        {"run1": ["trace_viewer"], "run2": ["trace_viewer"]} for the example.
    """
    # TODO(ioeric): use the following structure and use EventMultiplexer so that
    # the plugin still works when logdir is set to root_logdir/run1/
    #     root_logdir/
    #       run1/
    #         plugins/
    #           profile/
    #             host1.trace
    #       run2/
    #         plugins/
    #           profile/
    #             host2.trace
    run_to_tools = {}
    if not tf.gfile.IsDirectory(self.plugin_logdir):
      return run_to_tools
    for run in tf.gfile.ListDirectory(self.plugin_logdir):
      run_dir = self._run_dir(run)
      if not run_dir:
        continue
      run_to_tools[run] = []
      for tool in TOOLS:
        tool_pattern = '*' + TOOLS[tool]
        path = os.path.join(run_dir, tool_pattern)
        try:
          files = tf.gfile.Glob(path);
          if len(files) >= 1:
            run_to_tools[run].append(tool)
        except tf.errors.OpError:
            logging.warning("Cannot read asset directory: %s, OpError %s",
                            run_dir, e)
    return run_to_tools

  @wrappers.Request.application
  def tools_route(self, request):
    run_to_tools = self.index_impl()
    return http_util.Respond(request, run_to_tools, 'application/json')

  def host_impl(self, run, tool):
    """Returns available hosts for the run and tool in the log directory.

    In the plugin log directory, each directory contains profile data for a
    single run (identified by the directory name), and files in the run
    directory contains data for different tools and hosts. The file that
    contains profile for a specific tool "x" will have a prefix name TOOLS["x"].

    Example:
      log/
        run1/
          plugins/
            profile/
              host1.trace
              host2.trace
        run2/
          plugins/
            profile/
              host1.trace
              host2.trace

    Returns:
      A list of host names e.g.
        {"host1", "host2", "host3"} for the example.
    """
    tool_to_hosts = {}
    if not tf.gfile.IsDirectory(self.plugin_logdir):
      return tool_to_hosts
    run_dir = self._run_dir(run)
    if not run_dir:
       logging.warning("Cannot find asset directory: %s", run_dir)
       return;
    tool_pattern = '*' + TOOLS[tool]
    try:
      files = tf.gfile.Glob(os.path.join(run_dir,tool_pattern))
      tool_to_hosts = [os.path.basename(f).replace(TOOLS[tool],'') for f in files]
    except tf.errors.OpError:
      logging.warning("Cannot read asset directory: %s, OpError %s",
                        run_dir, e)
    return tool_to_hosts


  @wrappers.Request.application
  def hosts_route(self, request):
    run = request.args.get('run')
    tool = request.args.get('tag')
    tool_to_hosts = self.host_impl(run, tool)
    return http_util.Respond(request, tool_to_hosts, 'application/json')

  def data_impl(self, run, tool, host):
    """Retrieves and processes the tool data for a run and a host.

    Args:
      run: Name of the run.
      tool: Name of the tool.
      host: Name of the host.

    Returns:
      A string that can be served to the frontend tool or None if tool,
        run or host is invalid.
    """
    # Path relative to the path of plugin directory.
    if tool not in TOOLS:
      return None
    tool_name = str(host) + TOOLS[tool]
    rel_data_path = os.path.join(run, tool_name)
    asset_path = os.path.join(self.plugin_logdir, rel_data_path)
    raw_data = None
    try:
      with tf.gfile.Open(asset_path, "rb") as f:
        raw_data = f.read()
    except tf.errors.NotFoundError:
      logging.warning("Asset path %s not found", asset_path)
    except tf.errors.OpError as e:
      logging.warning("Couldn't read asset path: %s, OpError %s", asset_path, e)

    if raw_data is None:
      return None
    if tool == 'trace_viewer':
      return process_raw_trace(raw_data)
    if tool in _RAW_DATA_TOOLS:
      return raw_data
    return None

  @wrappers.Request.application
  def data_route(self, request):
    # params
    #   run: The run name.
    #   tag: The tool name e.g. trace_viewer. The plugin returns different UI
    #     data for different tools of the same run.
    #   host: The host name. 
    run = request.args.get('run')
    tool = request.args.get('tag')
    host = request.args.get('host')
    data = self.data_impl(run, tool, host)
    if data is None:
      return http_util.Respond(request, '404 Not Found', 'text/plain', code=404)
    return http_util.Respond(request, data, 'text/plain')

  def get_plugin_apps(self):
    return {
        LOGDIR_ROUTE: self.logdir_route,
        TOOLS_ROUTE: self.tools_route,
        HOSTS_ROUTE: self.hosts_route,
        DATA_ROUTE: self.data_route,
    }

  def is_active(self):
    """The plugin is active iff any run has at least one active tool/tag."""
    return any(self.index_impl().values())
