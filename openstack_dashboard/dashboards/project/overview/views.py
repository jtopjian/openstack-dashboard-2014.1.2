# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from django.template.defaultfilters import capfirst  # noqa
from django.template.defaultfilters import floatformat  # noqa
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView  # noqa

from horizon.utils import csvbase

from openstack_dashboard import usage


class ProjectUsageCsvRenderer(csvbase.BaseCsvResponse):

    columns = [_("Instance Name"), _("VCPUs"), _("Ram (MB)"),
               _("Disk (GB)"), _("Usage (Hours)"),
               _("Uptime(Seconds)"), _("State")]

    def get_row_data(self):

        for inst in self.context['usage'].get_instances():
            yield (inst['name'],
                   inst['vcpus'],
                   inst['memory_mb'],
                   inst['local_gb'],
                   floatformat(inst['hours'], 2),
                   inst['uptime'],
                   capfirst(inst['state']))


class ProjectOverview(usage.UsageView):
    table_class = usage.ProjectUsageTable
    usage_class = usage.ProjectUsage
    template_name = 'project/overview/usage.html'
    csv_response_class = ProjectUsageCsvRenderer

    def get_data(self):
        super(ProjectOverview, self).get_data()
        # jt
        from openstack_dashboard import api
        project_id = self.request.user.tenant_id

        # images
        owned_image_count = api.jt.get_image_count(project_id, self.request)
        image_limit = api.jt.get_image_quota(project_id)
        self.usage.limits['images'] = {'used': owned_image_count, 'quota': image_limit}

        # expiration
        self.usage.limits['expiration'] = api.jt.get_expiration_date(project_id)

        # start date
        self.usage.limits['start_date'] = api.jt.get_start_date(project_id)

        # dair notice
        dair_notice = api.jt.get_dair_notice(project_id)
        if dair_notice is not None:
            dair_notice = dair_notice.strip()
            if dair_notice != "":
                self.usage.limits['dair_notice'] = dair_notice

        # object storage
        object_mb_usage = api.jt.get_object_mb_usage(project_id)
        object_mb_limit = api.jt.get_object_mb_quota(project_id)
        self.usage.limits['object_mb'] = {'used': object_mb_usage, 'quota': object_mb_limit}

        return self.usage.get_instances()


class WarningView(TemplateView):
    template_name = "project/_warning.html"
