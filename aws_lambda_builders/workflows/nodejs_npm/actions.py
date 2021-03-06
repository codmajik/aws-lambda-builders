"""
Action to resolve NodeJS dependencies using NPM
"""

import json
import logging

from aws_lambda_builders.actions import BaseAction, Purpose, ActionFailedError
from .npm import NpmExecutionError

LOG = logging.getLogger(__name__)


class NodejsNpmPackAction(BaseAction):

    """
    A Lambda Builder Action that packages a Node.js package using NPM to extract the source and remove test resources
    """

    NAME = 'NpmPack'
    DESCRIPTION = "Packaging source using NPM"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, artifacts_dir, scratch_dir, manifest_path, osutils, subprocess_npm):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory where to store the output.
            Note that the actual result will be in the 'package' subdirectory here.

        :type scratch_dir: str
        :param scratch_dir: an existing (writable) directory for temporary files

        :type manifest_path: str
        :param manifest_path: path to package.json of an NPM project with the source to pack

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper
        """
        super(NodejsNpmPackAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.manifest_path = manifest_path
        self.scratch_dir = scratch_dir
        self.osutils = osutils
        self.subprocess_npm = subprocess_npm

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM packaging fails
        """
        try:
            package_path = "file:{}".format(self.osutils.abspath(self.osutils.dirname(self.manifest_path)))

            LOG.debug("NODEJS packaging %s to %s", package_path, self.scratch_dir)

            tarfile_name = self.subprocess_npm.run(['pack', '-q', package_path], cwd=self.scratch_dir)

            LOG.debug("NODEJS packed to %s", tarfile_name)

            tarfile_path = self.osutils.joinpath(self.scratch_dir, tarfile_name)

            LOG.debug("NODEJS extracting to %s", self.artifacts_dir)

            self.osutils.extract_tarfile(tarfile_path, self.artifacts_dir)

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))


class NodejsNpmInstallAction(BaseAction):

    """
    A Lambda Builder Action that installs NPM project dependencies
    """

    NAME = 'NpmInstall'
    DESCRIPTION = "Installing dependencies from NPM"
    PURPOSE = Purpose.RESOLVE_DEPENDENCIES

    def __init__(self, artifacts_dir, subprocess_npm):
        """
        :type artifacts_dir: str
        :param artifacts_dir: an existing (writable) directory with project source files.
            Dependencies will be installed in this directory.

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper
        """

        super(NodejsNpmInstallAction, self).__init__()
        self.artifacts_dir = artifacts_dir
        self.subprocess_npm = subprocess_npm

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """

        try:
            LOG.debug("NODEJS installing in: %s", self.artifacts_dir)

            self.subprocess_npm.run(
                    ['install', '-q', '--no-audit', '--no-save', '--production'],
                    cwd=self.artifacts_dir
            )

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))

class NodejsNpmScriptAction(BaseAction):

    """
    A Lambda Builder Action that conditionally runs a script in the package.json manifest
    """

    NAME = 'NpmScriptAction'
    DESCRIPTION = "Running a script"
    PURPOSE = Purpose.COPY_SOURCE

    def __init__(self, working_dir, manifest_path, script_name, subprocess_npm, osutils):
        """
        :type working_dir: str
        :param working_dir: Directory where the command will be executed.

        :type manifest_path: str
        :param manifest_path: Path to package.json

        :type script_name: str
        :param script_name: Name of an NPM script to execute

        :type subprocess_npm: aws_lambda_builders.workflows.nodejs_npm.npm.SubprocessNpm
        :param subprocess_npm: An instance of the NPM process wrapper

        :type osutils: aws_lambda_builders.workflows.nodejs_npm.utils.OSUtils
        :param osutils: An instance of OS Utilities for file manipulation
        """

        super(NodejsNpmScriptAction, self).__init__()
        self.working_dir = working_dir
        self.subprocess_npm = subprocess_npm
        self.manifest_path = manifest_path
        self.script_name = script_name
        self.osutils = osutils

    def execute(self):
        """
        Runs the action.

        :raises lambda_builders.actions.ActionFailedError: when NPM execution fails
        """

        try:
            manifest_contents = self.osutils.get_text_contents(self.manifest_path)
            parsed_json = json.loads(manifest_contents)

            if "scripts" in parsed_json.keys() and self.script_name in parsed_json["scripts"].keys():
                LOG.debug("NODEJS running 'npm run %s' in %s", self.script_name, self.working_dir)

                result = self.subprocess_npm.run(
                    ['run', self.script_name],
                    cwd=self.working_dir
                )

                LOG.debug("NODEJS 'npm run %s' result: %s", self.script_name, result)

        except NpmExecutionError as ex:
            raise ActionFailedError(str(ex))

        except ValueError as ex:
            # Python 2.7 doesn't have JSONDecoderError
            raise ActionFailedError("{} is not valid json: {}".format(self.manifest_path, str(ex)))
