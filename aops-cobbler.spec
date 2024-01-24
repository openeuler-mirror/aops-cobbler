Name:		aops-cobbler
Version:	v1.0.0
Release:	1
Summary:	A cobbler manager service used for one click automatic installation of the operating system.
License:	MulanPSL2
URL:		https://gitee.com/openeuler/%{name}
Source0:	%{name}-%{version}.tar.gz


BuildRequires:  python3-setuptools
Requires:   python3-flask python3-flask-restful python3-gevent python3-cryptography
Requires:   python3-requests python3-uWSGI python3-werkzeug python3-Flask-APScheduler
Requires:   python3-PyMySQL python3-sqlalchemy python3-concurrent-log-handler
Provides:   aops-cobbler
Conflicts:  aops-manager


%description
A cobbler manager service used for one click automatic installation of the operating system.


%prep
%autosetup -n %{name}-%{version}


# build for aops-cobbler
%py3_build


# install for aops-cobbler
%py3_install
mkdir -p %{buildroot}/opt/aops/
cp -r script %{buildroot}/opt/aops/


%files
%doc README.*
%attr(0644,root,root) %{_sysconfdir}/aops/aops-cobbler.ini
%attr(0755,root,root) %{_bindir}/aops-cobbler
%attr(0755,root,root) %{_unitdir}/aops-cobbler.service
%{python3_sitelib}/aops_cobbler*.egg-info
%{python3_sitelib}/cobbled/*
%attr(0755, root, root) /opt/aops/script/*


%changelog
