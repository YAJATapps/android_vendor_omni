#!/usr/bin/env python

# Copyright (C) 2013 Cybojenix <anthonydking@gmail.com>
# Copyright (C) 2013 The OmniROM Project
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
import json
import sys
import os
import os.path
import re
from xml.etree import ElementTree as ES
# Use the urllib importer from the Cyanogenmod roomservice
try:
    # For python3
    import urllib.request
except ImportError:
    # For python2
    import imp
    import urllib2
    urllib = imp.new_module('urllib')
    urllib.request = urllib2

# Config
# set this to the default remote to use in repo
default_rem = "omnirom2"
# set this to the default revision to use (branch/tag name)
default_rev = "android-12.1"
# set this to the remote that you use for projects from your team repos
# example fetch="https://github.com/omnirom"
default_team_rem = "omnirom2"
# this shouldn't change unless google makes changes
local_manifest_dir = ".repo/local_manifests"
# change this to your name on github (or equivalent hosting)
android_team = "omnirom"
# url to gerrit repository
gerrit_url = "gerrit.omnirom.org"


def check_repo_exists(git_data, device):
    if device.count("_") < 2:
        re_match = "^android_device_.*_{device}$".format(device=device)
    else:
        re_match = "^android_device.*_{device}$".format(device=device)

    matches = list(filter(lambda x: re.match(re_match, x), git_data))

    if len(matches) != 1:
        raise Exception("{device} not found,"
                        "exiting roomservice".format(device=device))

    return git_data[matches[0]]


def search_gerrit_for_device(device):
    # TODO: In next gerrit release regex search with r= should be supported!
    git_search_url = "https://{gerrit_url}/projects/?m={device}".format(
        gerrit_url=gerrit_url,
        device=device
    )
    git_req = urllib.request.Request(git_search_url)
    try:
        response = urllib.request.urlopen(git_req)
    except urllib.request.HTTPError:
        print("There was an issue connecting to gerrit."
              " Please try again in a minute")
    except urllib.request.URLError:
        print("WARNING: No network connection available.")
    else:
        # Skip silly gerrit "header"
        response.readline()
        git_data = json.load(response)
        device_data = check_repo_exists(git_data, device)
        print("found the {} device repo".format(device))
        return device_data


def parse_device_directory(device_url, device):
    if device.count("_") < 2:
        pattern = "^android_device_(?P<vendor>.+)_{}$".format(device)
    else:
        pattern = "^android_device_{}$".format(device)

    match = re.match(pattern, device_url)

    if match is None:
        raise Exception("Invalid project name {}".format(device_url))

    if device.count('_') < 2:
        return "device/{vendor}/{device}".format(
            vendor=match.group('vendor'),
            device=device,
        )
    else:
        vendor = device.split('_')[0]
        return "device/{vendor}/{device}".format(
            vendor=vendor,
            device=device,
        )


# Thank you RaYmAn
def iterate_manifests():
    files = []
    for file in os.listdir(local_manifest_dir):
        if file.endswith(".xml"):
            files.append(os.path.join(local_manifest_dir, file))
    files.append('.repo/manifest.xml')
    for file in files:
        try:
            man = ES.parse(file)
            man = man.getroot()
        except (IOError, ES.ParseError):
            print("WARNING: error while parsing %s" % file)
        else:
            for project in man.findall("project"):
                yield project


def iterate_manifests_remove_project():
    files = []
    for file in os.listdir(local_manifest_dir):
        if file.endswith(".xml"):
            files.append(os.path.join(local_manifest_dir, file))
    files.append('.repo/manifest.xml')
    for file in files:
        try:
            man = ES.parse(file)
            man = man.getroot()
        except (IOError, ES.ParseError):
            print("WARNING: error while parsing %s" % file)
        else:
            for project in man.findall("remove-project"):
                yield project

def check_project_exists(url, revision, path):
    for project in iterate_manifests():
        if project.get("name") == url \
                and project.get("revision") == revision \
                and project.get("path") == path:
            return True
    return False


def check_remove_project_exists(url):
    for project in iterate_manifests_remove_project():
        if project.get("name") == url:
            return True
    return False

def check_target_exists(directory):
    return os.path.isdir(directory)


# Use the indent function from http://stackoverflow.com/a/4590052
def indent(elem, level=0):
    i = ''.join(["\n", level*"  "])
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = ''.join([i, "  "])
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def create_manifest_project(url, directory,
                            remote=default_rem,
                            revision=default_rev):
    project_exists = check_project_exists(url, revision, directory)

    if project_exists:
        return None

    project = ES.Element("project",
                         attrib={
                             "path": directory,
                             "name": url,
                             "remote": remote,
                             "revision": revision
                         })
    return project

def create_remove_project(url):
    remove_project_exists = check_remove_project_exists(url)

    if remove_project_exists:
        return None

    project = ES.Element("remove-project",
                         attrib={
                             "name": url
                         })
    return project

def append_to_manifest(project):
    try:
        lm = ES.parse('/'.join([local_manifest_dir, "roomservice.xml"]))
        lm = lm.getroot()
    except (IOError, ES.ParseError):
        lm = ES.Element("manifest")
    lm.append(project)
    return lm


def write_to_manifest(manifest):
    indent(manifest)
    raw_xml = ES.tostring(manifest).decode()
    raw_xml = ''.join(['<?xml version="1.0" encoding="UTF-8"?>\n'
                       '<!--Please do not manually edit this file-->\n',
                       raw_xml])

    with open('/'.join([local_manifest_dir, "roomservice.xml"]), 'w') as f:
        f.write(raw_xml)
    print("wrote the new roomservice manifest")


def parse_device_from_manifest(device):
    for project in iterate_manifests():
        name = project.get('name')
        if name.startswith("android_device_") and name.endswith(device):
            return project.get('path')
    return None


def parse_device_from_folder(device):
    search = []
    if not os.path.isdir("device"):
        os.mkdir("device")
    for sub_folder in os.listdir("device"):
        if os.path.isdir("device/%s/%s" % (sub_folder, device)):
            search.append("device/%s/%s" % (sub_folder, device))
    if len(search) > 1:
        print("multiple devices under the name %s. "
              "defaulting to checking the manifest" % device)
        location = parse_device_from_manifest(device)
    elif len(search) == 1:
        location = search[0]
    else:
        print("Your device can't be found in device sources..")
        location = parse_device_from_manifest(device)
    return location


def parse_dependency_file(location):
    dep_file = "omni.dependencies"
    dep_location = '/'.join([location, dep_file])
    if not os.path.isfile(dep_location):
        print("WARNING: %s file not found" % dep_location)
        sys.exit()
    try:
        with open(dep_location, 'r') as f:
            dependencies = json.loads(f.read())
    except ValueError:
        raise Exception("ERROR: malformed dependency file")
    return dependencies


# if there is any conflict with existing and new
# delete the roomservice.xml file and create new
def check_manifest_problems(dependencies):
    for dependency in dependencies:
        repository = dependency.get("repository")
        target_path = dependency.get("target_path")
        revision = dependency.get("revision", default_rev)

        # check for existing projects
        for project in iterate_manifests():
            if project.get("revision") is not None \
                    and project.get("path") is not None \
                    and project.get("path") == target_path \
                    and project.get("revision") != revision:
                print("WARNING: detected conflict in revisions for repository ",
                      repository)
                current_dependency = str(project.get(repository))
                file = ES.parse('/'.join([local_manifest_dir,
                                          "roomservice.xml"]))
                file_root = file.getroot()
                for current_project in file_root.findall('project'):
                    new_dependency = str(current_project.find('revision'))
                    if new_dependency == current_dependency:
                        file_root.remove(current_project)
                file.write('/'.join([local_manifest_dir, "roomservice.xml"]))
                return


def create_dependency_manifest(dependencies):
    projects = []
    for dependency in dependencies:
        repository = dependency.get("repository")
        target_path = dependency.get("target_path")
        revision = dependency.get("revision", default_rev)
        remote = dependency.get("remote", default_rem)
        override = dependency.get("override", None)
        remove = dependency.get("remove", None)

        if remove is not None:
            #print("found remove in ", repository)
            project = create_remove_project(remove)
            if project is not None:
                manifest = append_to_manifest(project)
                #print(ES.tostring(manifest).decode())
                write_to_manifest(manifest)
        else:
            if override is not None:
                #print("found override in ", repository)
                project = create_remove_project(override)
                if project is not None:
                    manifest = append_to_manifest(project)
                    #print(ES.tostring(manifest).decode())
                    write_to_manifest(manifest)

            # not adding an organization should default to android_team
            # only apply this to github
            if remote == "github":
                if "/" not in repository:
                    repository = '/'.join([android_team, repository])
            project = create_manifest_project(repository,
                                            target_path,
                                            remote=remote,
                                            revision=revision)
            if project is not None:
                manifest = append_to_manifest(project)
                write_to_manifest(manifest)
                projects.append(target_path)
    if len(projects) > 0:
        os.system("repo sync --force-sync --no-clone-bundle %s" % " ".join(projects))


def create_common_dependencies_manifest(dependencies):
    dep_file = "omni.dependencies"
    common_list = []
    if dependencies is not None:
        for dependency in dependencies:
            try:
                index = common_list.index(dependency['target_path'])
            except ValueError:
                index = None
            if index is None:
                common_list.append(dependency['target_path'])
                dep_location = '/'.join([dependency['target_path'], dep_file])
                if not os.path.isfile(dep_location):
                    sys.exit()
                else:
                    try:
                        with open(dep_location, 'r') as f:
                            common_deps = json.loads(f.read())
                    except ValueError:
                        raise Exception("ERROR: malformed dependency file")

                    if common_deps is not None:
                        print("Looking for dependencies on: ",
                              dependency['target_path'])
                        check_manifest_problems(common_deps)
                        create_dependency_manifest(common_deps)
                        create_common_dependencies_manifest(common_deps)


def fetch_dependencies(device):
    if device == "emulator":
        location = "vendor/omni/utils/omni_emulator"
    else:
        location = parse_device_from_folder(device)
    if location is None or not os.path.isdir(location):
        raise Exception("ERROR: could not find your device "
                        "folder location, bailing out")
    dependencies = parse_dependency_file(location)
    check_manifest_problems(dependencies)
    create_dependency_manifest(dependencies)
    create_common_dependencies_manifest(dependencies)
    fetch_device(device)


def check_device_exists(device):
    location = parse_device_from_folder(device)
    if location is None:
        return False
    return os.path.isdir(location)


def fetch_device(device):
    if check_device_exists(device):
        print("WARNING: Trying to fetch a device that's already there")
    git_data = search_gerrit_for_device(device)
    if git_data is not None:
        device_url = git_data['id']
        device_dir = parse_device_directory(device_url, device)
        project = create_manifest_project(device_url,
                                          device_dir,
                                          remote=default_team_rem)
        if project is not None:
            manifest = append_to_manifest(project)
            write_to_manifest(manifest)
        # In case a project was written to manifest, but never synced
        if project is not None or not check_target_exists(device_dir):
            print("syncing the device config")
            os.system('repo sync --force-sync --no-clone-bundle %s' % device_dir)


if __name__ == '__main__':
    if not os.path.isdir(local_manifest_dir):
        os.mkdir(local_manifest_dir)

    product = sys.argv[1]
    try:
        device = product[product.index("_") + 1:]
    except ValueError:
        device = product

    if len(sys.argv) > 2:
        deps_only = sys.argv[2]
    else:
        deps_only = False

    if not deps_only:
        fetch_device(device)
    fetch_dependencies(device)
