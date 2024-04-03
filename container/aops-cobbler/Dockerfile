FROM openeuler/openeuler:22.03-lts-sp1
WORKDIR /app
COPY *  /app/
RUN yum install hostname httpd dhcp tftp cobbler xinetd cobbler-web pykickstart fence-agents python3-pip aops-cobbler -y --setopt=reposdir=/app
RUN pip install validators -i https://pypi.tuna.tsinghua.edu.cn/simple/

RUN cp /usr/share/syslinux/pxelinux.0 /var/lib/cobbler/loaders/; \
cp /usr/share/syslinux/menu.c32 /var/lib/cobbler/loaders/; \
cp /usr/share/syslinux/libutil.c32 /var/lib/cobbler/loaders/; \
cp /usr/share/syslinux/libcom32.c32 /var/lib/cobbler/loaders/; \
cp /usr/share/syslinux/ldlinux.c32 /var/lib/cobbler/loaders/

RUN sed -i '/disable/s/yes/no/g' /etc/xinetd.d/tftp
RUN systemctl enable rsyncd; \
systemctl enable httpd; \
systemctl enable tftp; \
systemctl enable xinetd; \
systemctl enable dhcpd; \
systemctl enable cobblerd; \
systemctl enable aops-cobbler;

CMD ["/sbin/init"]