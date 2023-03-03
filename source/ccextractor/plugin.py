#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import hashlib
import logging
import mimetypes
import os
import stat
import jsonata

from configparser import NoSectionError, NoOptionError
from ccextractor.lib.ffmpeg import Parser, Probe
from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.ccextractor")


class Settings(PluginSettings):
    settings = {
        "limit_to_extensions": False,
        "allowed_extensions":  'ts',
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "limit_to_extensions": {
                "label": "Only run when the original source file matches specified extensions",
            },
            "allowed_extensions":  self.__set_allowed_extensions_form_settings(),
        }

    def __set_allowed_extensions_form_settings(self):
        values = {
            "label": "Comma separated list of file extensions",
        }
        if not self.get_setting('limit_to_extensions'):
            values["display"] = 'hidden'
        return values


def file_ends_in_allowed_extensions(path, allowed_extensions):
    """
    Check if the file is in the allowed search extensions

    :return:
    """
    # Get the file extension
    file_extension = os.path.splitext(path)[-1][1:]

    # Ensure the file's extension is lowercase
    file_extension = file_extension.lower()

    # If the config is empty (not yet configured) ignore everything
    if not allowed_extensions:
        logger.debug("Plugin has not yet been configured with a list of file extensions to allow. Blocking everything.")
        return False

    # Check if it ends with one of the allowed search extensions
    if file_extension in allowed_extensions:
        return True

    logger.debug("File '{}' does not end in the specified file extensions '{}'.".format(path, allowed_extensions))
    return False


def file_already_processed(path):
    
    # Check for srt file with the same name as the video file
    file_dirname = os.path.dirname(path)
    file_sans_ext = os.path.splitext(os.path.basename(path))[0]
    ccextractor_file_out = "{}.srt".format(file_sans_ext)
     
    if os.path.exists(os.path.join(file_dirname, ccextractor_file_out)):
        logger.info("File was previously processed with ccextractor")
        # This stream already has been processed
        return True

    # Default to...
    return False
    
def build_ccextractor_args(abspath, settings):
    
    return [
        'ccextractor',
        abspath
    ]
    
    
def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.

    :param data:
    :return:

    """
    # Get settings
    settings = Settings(library_id=data.get('library_id'))
    
    # Get the path to the file
    abspath = data.get('path')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

    # Limit to configured file extensions
    if settings.get_setting('limit_to_extensions'):
        allowed_extensions = settings.get_setting('allowed_extensions')
        if not file_ends_in_allowed_extensions(abspath, allowed_extensions):
            return data

    if not file_already_processed(abspath):
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.debug("File has not been processed previously '{}'. It should be added to task list.".format(abspath))

    return data
    
    
def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        worker_log              - Array, the log lines that are being tailed by the frontend. Can be left empty.
        library_id              - Number, the library that the current task is associated with.
        exec_command            - Array, a subprocess command that Unmanic should execute. Can be empty.
        command_progress_parser - Function, a function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - String, the source file to be processed by the command.
        file_out                - String, the destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - String, the absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:
    
    """
# Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the file paths
    file_in = data.get('file_in')
    file_out = data.get('file_out')
    original_file_path = data.get('original_file_path')
    
    # Get settings
    settings = Settings(library_id=data.get('library_id'))
    
    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(file_in):
        # File probe failed, skip the rest of this test
        return data

    # Limit to configured file extensions
    # Unlike other plugins, this is checked against the original file path, not what is currently cached
    if settings.get_setting('limit_to_extensions'):
        allowed_extensions = settings.get_setting('allowed_extensions')
        if not file_ends_in_allowed_extensions(original_file_path, allowed_extensions):
            return data

    if not file_already_processed(original_file_path):
        # Check what we are running...
        # Build args
        args = build_ccextractor_args(file_in, settings)
        
        probe_info = probe.get_probe()
        file_probe_streams = probe_info.get('streams')
        if not file_probe_streams:
            return False
        
        # Report probe data for debug purpose
        logger.debug("Probe stream report : {}".format(file_probe_streams))

        discovered_values = False
        context = jsonata.Context()
        
        # Check if subtitle or data is present, if not dont execute ccextractor
        if context('$exists(streams[codec_type="data"][0].codec_type)', probe_info):
            discovered_values = context('$.streams[codec_type="data"][0].codec_name', probe_info)
            logger.info("Data found : {}".format(discovered_values))
        elif context('$exists(streams[codec_type="subtitle"][0].codec_type)', probe_info):
            discovered_values = context('$.streams[codec_type="subtitle"][0].codec_name', probe_info)
            logger.info("Subtitle found : {}".format(discovered_values))
        else:
            logger.info("No subtitle found")
            
        # Excute CCextractor only if data or subtitle are found
        if discovered_values:
            # Set the parser
            parser = Parser(logger)
            parser.set_probe(probe)
            data['command_progress_parser'] = parser.parse_progress
            
            logger.info("Execute CCextractor for {}.".format(file_in))
            data['exec_command'] = args        
            
            # Mark file as being processed for post-processor
            src_file_hash = hashlib.md5(original_file_path.encode('utf8')).hexdigest()
            profile_directory = settings.get_profile_directory()
            plugin_file_lockfile = os.path.join(profile_directory, '{}.lock'.format(src_file_hash))
            with open(plugin_file_lockfile, 'w') as f:
                 pass

        
    return data
