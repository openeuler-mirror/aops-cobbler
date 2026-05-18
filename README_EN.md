# aops-cobbler

## Overview

An important service of the intelligent O&M platform A-Ops, providing automated OS installation. It interacts with the Cobbler server in a unified manner and manages Cobbler-related configurations.

## Environment Requirements

+ Python 3.9.9 or later
+ MySQL 8.0

## Local Development Environment Setup

1. Clone this repository and development kits.

   ```shell
   git clone https://gitee.com/aops-cobbler.git
   ```

2. Open the project using PyCharm or other preferred development tools.

3. Run the following commands in sequence to install or upgrade the pip utility and install the dependencies required for the project:
   
   ```shell
   python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/
   pip install flask_apscheduler validators cryptography PyMySQL sqlalchemy flask gevent werkzeug concurrent_log_handler -i https://pypi.tuna.tsinghua.edu.cn/simple/
   ```

4. Configure the service.<br>
   (1) In the `cobbler/conf/constant.py` file, change the value of `BASE_CONFIG_PATH` to the actual local path to the service configuration file `aops-cobbler.ini`.<br>
   (2) In the service configuration file `/aops-cobbler/conf/aops-cobbler.ini`, change the path to the corresponding local path.

5. Start the development server.

   ```shell
   python3 manage.py
   ```

   Access the project at `http://127.0.0.1:8888`.

## RPM Build

1. Run the following command to package the aops-cobbler source code into a `.tar.gz` archive. The file name must be identical to the `Source0` field in the `.spec` file:

   ```shell
   git archive master --format=tar.gz --output=D:/opt/cobbler/aops-cobbler-v1.0.0.tar.gz
   ```

2. Run the following commands in sequence to install the rpmdevtools utility and generate a standard workspace in the `/root` directory (or `/home/username` for non-root users):

   ```shell
   yum -y install rpmdevtools*
   rpmdev-setuptree
   ```

3. Upload the `.tar.gz` source archive to the `SOURCES` directory and the `.spec` file to the `SPECS` directory.

4. Run the following command to convert the file format:
   
   ```shell
   dos2unix -n aops-cobbler.spec aops-cobbler.spec
   ```

   If the command does not exist, run the following command to install it:

   ```shell
   yum install -y dos2unix
   ```

5. Run the following command to build an RPM package:

   ```shell
   rpmbuild -ba rpmbuild/SPECS/aops-cobbler.spec
   ```

## Installation and Deployment

1. Run the following command to install the RPM package and its required dependencies:

   ```shell
   yum localinstall -y aops-cobbler-v1.0.0-1.x86_64.rpm
   dos2unix -n /usr/bin/aops-cobbler /usr/bin/aops-cobbler (Optional. The local source archive may contain newline characters.)
   ```

2. Confirm that the `raw_host` table has been created. The SQL statement can be found in `/database/aops-cobbler.sql`.

3. Edit the `/etc/aops/aops-cobbler.ini` file:<br>
   a. Change the IP address and port number of the node where aops-cobbler is deployed.<br>
   b. Change the API address of the Cobbler server.<br>
   c. Modify the MySQL connection information.<br>
   d. Modify the available range of IP address segments.<br>
   1. Retain the default settings for other configurations or modify them as required.

4. Execute the following commands respectively to start the service, verify if the startup was successful, view the startup logs, check if the process is running, and confirm if the port is enabled.
   
   ```shell
   systemctl start aops-cobbler
   systemctl status aops-cobbler
   tail -200f /var/log/aops/uwsgi/aops-cobbler.log
   ps -ef | grep '/opt/aops/uwsgi/cobbled.ini'
   netstat -anp | grep <port_number>
   ```

5. Use a tool such as Postman to call the API and verify that the service is available.

## Service Stopping and Uninstallation

1. Run the following commands in sequence to stop the service and check whether the service was stopped successfully:

   ```shell
   systemctl stop aops-cobbler
   systemctl status aops-cobbler
   ```

2. Uninstall the RPM package.

   ```shell
   yum remove -y aops-cobbler-v1.0.0-1.x86_64
   ```

## Common Files

1. Service configuration file: `/etc/aops/aops-cobbler.ini`
2. Service run logs: `/var/log/aops/cobbler/aops-cobbler.log`
3. uWSGI configuration file: `/opt/aops/uwsgi/cobbled.ini`
4. uWSGI run logs: `/var/log/aops/uwsgi/aops-cobbler.log`

## Contribution

1. Fork this repository.
2. Create a Feat_*xxx* branch.
3. Commit code.
4. Create a pull request (PR).
