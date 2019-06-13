# Since our cli produces unicode output, but we want tests in python2 as well
from __future__ import unicode_literals

from click.testing import CliRunner
import great_expectations.version
from great_expectations.cli import cli
import tempfile
import pytest
import json
import os
import shutil
from ruamel.yaml import YAML
yaml = YAML()
yaml.default_flow_style = False

try:
    from unittest import mock
except ImportError:
    import mock


def test_cli_command_entrance():
    runner = CliRunner()

    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert result.output == """Usage: cli [OPTIONS] COMMAND [ARGS]...

  great_expectations command-line interface

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  init      Initialze a new Great Expectations project.
  profile   Profile a great expectations object.
  render    Render a great expectations object.
  validate  Validate a CSV file against an expectations configuration.
"""


def test_cli_command_bad_command():
    runner = CliRunner()

    result = runner.invoke(cli, ["blarg"])
    assert result.exit_code == 2
    assert result.output == """Usage: cli [OPTIONS] COMMAND [ARGS]...
Try "cli --help" for help.

Error: No such command "blarg".
"""


def test_cli_validate_help():
    runner = CliRunner()

    result = runner.invoke(cli, ["validate", "--help"])

    assert result.exit_code == 0
    expected_help_message = """Usage: cli validate [OPTIONS] DATASET EXPECTATIONS_CONFIG_FILE

  Validate a CSV file against an expectations configuration.

  DATASET: Path to a file containing a CSV file to validate using the 
  provided expectations_config_file.

  EXPECTATIONS_CONFIG_FILE: Path to a file containing a valid
  great_expectations expectations config to use to validate the data.

Options:
  -p, --evaluation_parameters TEXT
                                  Path to a file containing JSON object used
                                  to evaluate parameters in expectations
                                  config.
  -o, --result_format TEXT        Result format to use when building
                                  evaluation responses.
  -e, --catch_exceptions BOOLEAN  Specify whether to catch exceptions raised
                                  during evaluation of expectations (defaults
                                  to True).
  -f, --only_return_failures BOOLEAN
                                  Specify whether to only return expectations
                                  that are not met during evaluation
                                  (defaults to False).
  -m, --custom_dataset_module TEXT
                                  Path to a python module containing a custom
                                  dataset class.
  -c, --custom_dataset_class TEXT
                                  Name of the custom dataset class to use
                                  during evaluation.
  --help                          Show this message and exit.
""".replace(" ", "").replace("\t", "").replace("\n", "")
    output = str(result.output).replace(
        " ", "").replace("\t", "").replace("\n", "")
    assert output == expected_help_message


def test_cli_validate_missing_positional_arguments():
    runner = CliRunner()

    result = runner.invoke(cli, ["validate"])

    assert "Error: Missing argument \"DATASET\"." in str(result.output)


def test_cli_version():
    runner = CliRunner()

    result = runner.invoke(cli, ["--version"])
    assert great_expectations.version.__version__ in str(result.output)


def test_validate_basic_operation():
    with mock.patch("uuid.uuid1") as mock_uuid:
        mock_uuid.return_value = "__autogenerated_uuid_v1__"
        runner = CliRunner()
        with pytest.warns(UserWarning, match="No great_expectations version found in configuration object."):
            result = runner.invoke(cli, ["validate", "./tests/test_sets/Titanic.csv",
                                         "./tests/test_sets/titanic_expectations.json"])

            assert result.exit_code == 1
            json_result = json.loads(str(result.output))

    del json_result["meta"]["great_expectations.__version__"]
    with open('./tests/test_sets/expected_cli_results_default.json', 'r') as f:
        expected_cli_results = json.load(f)

    assert json_result == expected_cli_results


def test_validate_custom_dataset():
    with mock.patch("uuid.uuid1") as mock_uuid:
        mock_uuid.return_value = "__autogenerated_uuid_v1__"
        runner = CliRunner()
        with pytest.warns(UserWarning, match="No great_expectations version found in configuration object."):
            result = runner.invoke(cli, ["validate",
                                         "./tests/test_sets/Titanic.csv",
                                         "./tests/test_sets/titanic_custom_expectations.json",
                                         "-f", "True",
                                         "-m", "./tests/test_fixtures/custom_dataset.py",
                                         "-c", "CustomPandasDataset"])

            json_result = json.loads(result.output)

    del json_result["meta"]["great_expectations.__version__"]
    del json_result["results"][0]["result"]['partial_unexpected_counts']
    with open('./tests/test_sets/expected_cli_results_custom.json', 'r') as f:
        expected_cli_results = json.load(f)

    assert json_result == expected_cli_results


def test_cli_evaluation_parameters(capsys):
    with pytest.warns(UserWarning, match="No great_expectations version found in configuration object."):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate",
                                     "./tests/test_sets/Titanic.csv",
                                     "./tests/test_sets/titanic_parameterized_expectations.json",
                                     "--evaluation_parameters",
                                     "./tests/test_sets/titanic_evaluation_parameters.json",
                                     "-f", "True"])
        json_result = json.loads(result.output)

    with open('./tests/test_sets/titanic_evaluation_parameters.json', 'r') as f:
        expected_evaluation_parameters = json.load(f)

    assert json_result['evaluation_parameters'] == expected_evaluation_parameters


def test_cli_init(tmp_path_factory):
    basedir = tmp_path_factory.mktemp("test_cli_init_diff")
    basedir = str(basedir)
    os.makedirs(os.path.join(basedir, "data"))
    curdir = os.path.abspath(os.getcwd())
    os.chdir(basedir)

    runner = CliRunner()
    result = runner.invoke(cli, ["init"], input="Y\n1\n%s\n\n" % str(
        os.path.join(basedir, "data")))

    print(result.output)

    assert """Always know what to expect from your data.""" in result.output

    assert os.path.isdir(os.path.join(basedir, "great_expectations"))
    assert os.path.isfile(os.path.join(
        basedir, "great_expectations/great_expectations.yml"))
    config = yaml.load(
        open(os.path.join(basedir, "great_expectations/great_expectations.yml"), "r"))
    assert config["datasources"]["data"]["type"] == "pandas"

    os.chdir(curdir)

    # assert False


# def test_cli_render(tmp_path_factory):
#     runner = CliRunner()
#     result = runner.invoke(cli, ["render"])

#     print(result)
#     print(result.output)
#     assert False


def test_cli_profile(empty_data_context, filesystem_csv_2):
    empty_data_context.add_datasource(
        "my_datasource", "pandas", base_directory=str(filesystem_csv_2))
    not_so_empty_data_context = empty_data_context

    # print(not_so_empty_data_context.get_available_data_asset_names())

    project_root_dir = not_so_empty_data_context.get_context_root_directory()
    # print(project_root_dir)

    runner = CliRunner()
    result = runner.invoke(
        cli, ["profile", "my_datasource", "-d", project_root_dir])

    # print(result)
    # print(result.output)

    assert "Profiling my_datasource with BasicDatasetProfiler" in result.output
    assert "Note: You will need to review and revise Expectations before using them in production." in result.output
