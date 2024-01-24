# aops-cobbler

### 介绍
智能运维平台aops的一个重要组成服务，提供一键自动安装操作系统功能，负责统一跟Cobbler服务端进行交互，管理Cobbler相关配置。

### 环境需求
+ Python 3.9.9+
+ MySql 8.0


### 本地开发环境搭建

1. 克隆此仓库与开发工具包

   ```
   git clone https://gitee.com/aops-cobbler.git
   ```

2. 使用PyCharm等开发工具打开该项目

3. 安装项目运行所需依赖库，先后通过以下命令安装或者升级pip组件、安装项目所需依赖。
   ```
   python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/
   pip install flask_apscheduler validators cryptography PyMySQL sqlalchemy flask gevent werkzeug concurrent_log_handler -i https://pypi.tuna.tsinghua.edu.cn/simple/
   ```

4. 服务配置<br>
   (1) 修改cobbler/conf/constant.py文件，将配置项BASE_CONFIG_PATH的值修改成业务配置文件aops-cobbler.ini本地实际地址。<br>
   (2) 修改业务配置文件/aops-cobbler/conf/aops-cobbler.ini，修改成相应的本地地址。

5. 启动开发服务器

   ```
   python3 manage.py
   ```

   现在可访问`http://127.0.0.1:8888`访问项目

### 构建RPM包
1. 执行以下命令将aops-cobbler源码打成.tar.gz格式的压缩包，压缩包命名必须和spes文件中Source0完全一致
   ```
   git archive master --format=tar.gz --output=D:/opt/cobbler/aops-cobbler-v1.0.0.tar.gz
   ```
2. 先后执行以下命令安装rpmdevtools工具，并在“/root“目录（非root用户为“/home/用户名“目录）下生成一套标准化的“工作空间”。
   ```
   yum -y install rpmdevtools*
   rpmdev-setuptree
   ```
3. 上传.tar.gz格式的源码压缩包至SOURCES目录下，上传.spec文件至SPECS目录下。

4. 执行以下命令对文件格式进行转化
   ```
   dos2unix -n aops-cobbler.spec aops-cobbler.spec
   ```
   如果该命令不存在，请执行以下命令进行安装。
   ```
   yum install -y dos2unix
   ```
5. 执行以下命令构建RPM包。
   ```
   rpmbuild -ba rpmbuild/SPECS/aops-cobbler.spec
   ```

### 安装及部署
1. 执行以下命令安装该RPM包以及所需要的依赖。
   ```
   yum localinstall -y aops-cobbler-v1.0.0-1.x86_64.rpm
   dos2unix -n /usr/bin/aops-cobbler /usr/bin/aops-cobbler(非必须，本地打的源码压缩包可能存在换行符问题)
   ```
2. 确认raw_host表已创建，建表语句见 /database/aops-cobbler.sql

3. 编辑/etc/aops/aops-cobbler.ini文件:<br/>
   一、修改aops-cobbler当前部署节点IP及端口号<br/>
   二、修改Cobbler服务端API地址<br/>
   三、修改mysql连接信息<br/>
   四、修改IP网段资源可使用范围<br/>
   五、其他配置采用默认配置即可，也可以根据实际情况进行修改。

4. 分别执行以下命令启动服务、查看服务启动是否成功、查看服务启动日志、查看进程是否成功拉起、查看端口号是否已经启用
   ```
   systemctl start aops-cobbler
   systemctl status aops-cobbler
   tail -200f /var/log/aops/uwsgi/aops-cobbler.log
   ps -ef | grep '/opt/aops/uwsgi/cobbled.ini'
   netstat -anp | grep 端口号
   ```
5. 通过postman等工具调用接口，验证服务是否正常可用。

### 停止及卸载
1. 先后执行以下命令停止服务、查看服务停止是否成功。
   ```
   systemctl stop aops-cobbler
   systemctl status aops-cobbler
   ```
2. 卸载该RPM包
   ```
   yum remove -y aops-cobbler-v1.0.0-1.x86_64
   ```

### 常用文件
1. 业务配置文件：/etc/aops/aops-cobbler.ini
2. 业务运行日志：/var/log/aops/cobbler/aops-cobbler.log
3. uwsgi配置文件：/opt/aops/uwsgi/cobbled.ini
4. uwsgi运行日志：/var/log/aops/uwsgi/aops-cobbler.log

### 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request