#!/bin/bash

copy_aops_conf(){
    echo "[INFO] Create the /etc/aops/ folder and copy conf to the aops directory."
    mkdir -p /etc/aops/
    cp ./conf/aops-cobbler.ini /etc/aops/

    mkdir -p /etc/cobbler/
    cp ./conf/dhcp.template /etc/cobbler/
    cp ./conf/settings /etc/cobbler/

    mkdir -p /etc/cobbler/boot_loader_conf/
    cp ./conf/pxedefault.template /etc/cobbler/boot_loader_conf/

    mkdir -p /var/lib/cobbler/
    cp ./conf/distro_signatures.json /var/lib/cobbler/
}

prepare_dockerfile_repo(){
    echo "[INFO] Create the repo file for the dockerfile folder."
    cp ./conf/*.repo ./aops-cobbler/
}

docker_build(){
    copy_aops_conf
    prepare_dockerfile_repo
    docker-compose build --no-cache
    rm ./aops-cobbler/*.repo
}

install_docker_compose(){
    docker_compose_installed=`rpm -q docker-compose`
    if [ $? -ne 0 ] ; then
        dnf install docker-compose -y
    else
        echo "docker-compose is already installed."
    fi
    docker_installed=`rpm -q docker`
    if [ $? -ne 0 ] ; then
        dnf install docker -y
    else
        echo "docker is already installed."
    fi
}

main(){
    install_docker_compose
    while :
    do
        echo "===========================Container arrangement==========================="
        echo "1. Build the docker container (build)."
        echo "2. Start the container orchestration service (start-service)."
        echo "3. Stop all container services (stop-service)."
        echo "Enter to exit the operation (Q/q)."
        read -p "Select an operation procedure to continue: " operation
        case $operation in
            "build")
                docker_build
                docker image prune
            ;;
            "start-service")
                docker-compose up -d
            ;;
            "stop-service")
                docker-compose down
            ;;
            "Q")
                break
            ;;
            "q")
                break
            ;;
        esac
    done
}

main
