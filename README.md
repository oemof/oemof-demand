# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/oemof/oemof-demand/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                     |    Stmts |     Miss |   Branch |   BrPart |      Cover |   Missing |
|----------------------------------------- | -------: | -------: | -------: | -------: | ---------: | --------: |
| src/oemof/demand/\_\_init\_\_.py         |        4 |        0 |        0 |        0 |    100.00% |           |
| src/oemof/demand/bdew/\_\_init\_\_.py    |        8 |        0 |        0 |        0 |    100.00% |           |
| src/oemof/demand/bdew/\_profiles25.py    |       77 |        0 |        8 |        0 |    100.00% |           |
| src/oemof/demand/bdew/elec\_slp.py       |       72 |        0 |        8 |        0 |    100.00% |           |
| src/oemof/demand/bdew/heat\_building.py  |       86 |        6 |       12 |        4 |     87.76% |80, 132-135, 299, 310 |
| src/oemof/demand/config.py               |       74 |        0 |       20 |        0 |    100.00% |           |
| src/oemof/demand/particular\_profiles.py |       39 |        1 |        8 |        1 |     95.74% |       134 |
| src/oemof/demand/tools.py                |       18 |        0 |        8 |        0 |    100.00% |           |
| src/oemof/demand/vdi/\_\_init\_\_.py     |        5 |        0 |        0 |        0 |    100.00% |           |
| src/oemof/demand/vdi/dwd\_try.py         |       29 |        0 |        6 |        0 |    100.00% |           |
| src/oemof/demand/vdi/regions.py          |      190 |        0 |       48 |        0 |    100.00% |           |
| **TOTAL**                                |  **602** |    **7** |  **118** |    **5** | **98.06%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/oemof/oemof-demand/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/oemof/oemof-demand/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/oemof/oemof-demand/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/oemof/oemof-demand/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Foemof%2Foemof-demand%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/oemof/oemof-demand/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.