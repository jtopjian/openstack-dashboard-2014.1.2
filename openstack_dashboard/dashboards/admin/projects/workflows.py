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


from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon import workflows

from openstack_dashboard import api
from openstack_dashboard.api import base
from openstack_dashboard.api import cinder
from openstack_dashboard.api import keystone
from openstack_dashboard.api import nova
from openstack_dashboard.usage import quotas

# MJ
import datetime

INDEX_URL = "horizon:admin:projects:index"
ADD_USER_URL = "horizon:admin:projects:create_user"
PROJECT_GROUP_ENABLED = keystone.VERSIONS.active >= 3
PROJECT_USER_MEMBER_SLUG = "update_members"
PROJECT_GROUP_MEMBER_SLUG = "update_group_members"

# jt
def get_admin_tenant_id(request):
    tenants = api.keystone.tenant_list(request)[0]
    admin_tenant_id = [tenant.id for tenant in tenants if tenant.name == 'admin'][0]
    return admin_tenant_id

# jt
class UpdateDAIRAction(workflows.Action):
    expiration = forms.CharField(max_length=50, label=_("Expiration Date"))
    start_date = forms.CharField(max_length=50, label=_("Start Date"))
    dair_notice = forms.CharField(max_length=750, label=_("Notice from DAIR"), required=False)
    dair_notice_link = forms.CharField(max_length=750, label=_("Optional URL"), required=False)
    reseller_logo = forms.CharField(max_length=100, label=_("Reseller Logo"), required=False)
    #tm
    research_participant = forms.CharField(max_length=100, label=_("Research Software Participant"), required=False)

    def __init__(self, request, *args, **kwargs):
        super(UpdateDAIRAction, self).__init__(request,
                                               *args,
                                               **kwargs)
        if 'project_id' in args[0]:
            project_id = args[0]['project_id']
            self.fields['expiration'].initial = api.jt.get_expiration_date(project_id)
            self.fields['start_date'].initial = api.jt.get_start_date(project_id)
            self.fields['dair_notice'].initial = api.jt.get_dair_notice(project_id)
            self.fields['dair_notice_link'].initial = api.jt.get_dair_notice_link(project_id)
            self.fields['reseller_logo'].initial = api.jt.get_reseller_logo(project_id)
            self.fields['research_participant'].initial = api.jt.get_research_participant(project_id)
        else:
            start_date = datetime.date.today()
            future_expire_date = start_date.replace(year=start_date.year+1).strftime('%B %d, %Y')
            self.fields['start_date'].initial = start_date.strftime('%B %d, %Y')
            self.fields['expiration'].initial = future_expire_date
            self.fields['dair_notice'].initial = ''
            self.fields['dair_notice_link'].initial = ''
            self.fields['reseller_logo'].initial = ''
            #tm
            self.fields['research_participant'].initial = ''

    class Meta:
        name = _("DAIR")
        slug = 'update_dair'
        help_text = _("From here you can set DAIR information for the project.")

class UpdateDAIR(workflows.Step):
    action_class = UpdateDAIRAction
    depends_on = ("project_id",)
    contributes = ('expiration', 'start_date', 'dair_notice', 'dair_notice_link', 'reseller_logo','research_participant',)

class UpdateProjectQuotaAction(workflows.Action):
    ifcb_label = _("Injected File Content Bytes")
    metadata_items = forms.IntegerField(min_value=-1,
                                        label=_("Metadata Items"))
    cores = forms.IntegerField(min_value=-1, label=_("VCPUs"))
    instances = forms.IntegerField(min_value=-1, label=_("Instances"))
    injected_files = forms.IntegerField(min_value=-1,
                                        label=_("Injected Files"))
    injected_file_content_bytes = forms.IntegerField(min_value=-1,
                                                     label=ifcb_label)
    volumes = forms.IntegerField(min_value=-1, label=_("Volumes"))
    snapshots = forms.IntegerField(min_value=-1, label=_("Volume Snapshots"))
    gigabytes = forms.IntegerField(
        min_value=-1, label=_("Total Size of Volumes and Snapshots (GB)"))
    ram = forms.IntegerField(min_value=-1, label=_("RAM (MB)"))
    floating_ips = forms.IntegerField(min_value=-1, label=_("Floating IPs"))
    fixed_ips = forms.IntegerField(min_value=-1, label=_("Fixed IPs"))
    security_groups = forms.IntegerField(min_value=-1,
                                         label=_("Security Groups"))
    security_group_rules = forms.IntegerField(min_value=-1,
                                              label=_("Security Group Rules"))
    # jt
    object_mb = forms.IntegerField(min_value=0, label=_("Object Storage (MB)"))
    images = forms.IntegerField(min_value=0, label=_("Images"))

    # Neutron
    security_group = forms.IntegerField(min_value=-1,
                                        label=_("Security Groups"))
    security_group_rule = forms.IntegerField(min_value=-1,
                                             label=_("Security Group Rules"))
    floatingip = forms.IntegerField(min_value=-1, label=_("Floating IPs"))
    network = forms.IntegerField(min_value=-1, label=_("Networks"))
    port = forms.IntegerField(min_value=-1, label=_("Ports"))
    router = forms.IntegerField(min_value=-1, label=_("Routers"))
    subnet = forms.IntegerField(min_value=-1, label=_("Subnets"))

    def __init__(self, request, *args, **kwargs):
        super(UpdateProjectQuotaAction, self).__init__(request,
                                                       *args,
                                                       **kwargs)
        disabled_quotas = quotas.get_disabled_quotas(request)
        for field in disabled_quotas:
            if field in self.fields:
                self.fields[field].required = False
                self.fields[field].widget = forms.HiddenInput()

        # jt
        if 'project_id' in args[0]:
            project_id = args[0]['project_id']
            self.fields['images'].initial = api.jt.get_image_quota(project_id)
            self.fields['object_mb'].initial = api.jt.get_object_mb_quota(project_id)
        else:
            # MJ expiration autofill
            self.fields['images'].initial = 5
            self.fields['object_mb'].initial = 204800

    class Meta:
        name = _("Quota")
        slug = 'update_quotas'
        help_text = _("From here you can set quotas "
                      "(max limits) for the project.")


class UpdateProjectQuota(workflows.Step):
    action_class = UpdateProjectQuotaAction
    depends_on = ("project_id",)
    # jt
    #contributes = quotas.QUOTA_FIELDS
    QUOTA_FIELDS = quotas.QUOTA_FIELDS + ('object_mb', 'images',)
    contributes = QUOTA_FIELDS


class CreateProjectInfoAction(workflows.Action):
    # Hide the domain_id and domain_name by default
    domain_id = forms.CharField(label=_("Domain ID"),
                                required=False,
                                widget=forms.HiddenInput())
    domain_name = forms.CharField(label=_("Domain Name"),
                                  required=False,
                                  widget=forms.HiddenInput())
    name = forms.CharField(label=_("Name"),
                           max_length=64)
    description = forms.CharField(widget=forms.widgets.Textarea(),
                                  label=_("Description"),
                                  required=False)
    enabled = forms.BooleanField(label=_("Enabled"),
                                 required=False,
                                 initial=True)

    def __init__(self, request, *args, **kwargs):
        super(CreateProjectInfoAction, self).__init__(request,
                                                      *args,
                                                      **kwargs)
        # For keystone V3, display the two fields in read-only
        if keystone.VERSIONS.active >= 3:
            readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
            self.fields["domain_id"].widget = readonlyInput
            self.fields["domain_name"].widget = readonlyInput

    class Meta:
        name = _("Project Info")
        help_text = _("From here you can create a new "
                      "project to organize users.")


class CreateProjectInfo(workflows.Step):
    action_class = CreateProjectInfoAction
    contributes = ("domain_id",
                   "domain_name",
                   "project_id",
                   "name",
                   "description",
                   "enabled")


class UpdateProjectMembersAction(workflows.MembershipAction):
    def __init__(self, request, *args, **kwargs):
        super(UpdateProjectMembersAction, self).__init__(request,
                                                         *args,
                                                         **kwargs)
        err_msg = _('Unable to retrieve user list. Please try again later.')
        # Use the domain_id from the project
        domain_id = self.initial.get("domain_id", None)
        project_id = ''
        if 'project_id' in self.initial:
            project_id = self.initial['project_id']

        # Get the default role
        try:
            default_role = api.keystone.get_default_role(self.request)
            # Default role is necessary to add members to a project
            if default_role is None:
                default = getattr(settings,
                                  "OPENSTACK_KEYSTONE_DEFAULT_ROLE", None)
                msg = _('Could not find default role "%s" in Keystone') % \
                        default
                raise exceptions.NotFound(msg)
        except Exception:
            exceptions.handle(self.request,
                              err_msg,
                              redirect=reverse(INDEX_URL))
        default_role_name = self.get_default_role_field_name()
        self.fields[default_role_name] = forms.CharField(required=False)
        self.fields[default_role_name].initial = default_role.id

        # Get list of available users
        all_users = []
        try:
            all_users = api.keystone.user_list(request,
                                               domain=domain_id)
        except Exception:
            exceptions.handle(request, err_msg)
        users_list = [(user.id, user.name) for user in all_users]

        # Get list of roles
        role_list = []
        try:
            role_list = api.keystone.role_list(request)
        except Exception:
            exceptions.handle(request,
                              err_msg,
                              redirect=reverse(INDEX_URL))
        for role in role_list:
            field_name = self.get_member_field_name(role.id)
            label = role.name
            self.fields[field_name] = forms.MultipleChoiceField(required=False,
                                                                label=label)
            self.fields[field_name].choices = users_list
            self.fields[field_name].initial = []

        # Figure out users & roles
        if project_id:
            try:
                project_members = api.keystone.user_list(request,
                    project=project_id)
            except Exception:
                exceptions.handle(request, err_msg)

            for user in project_members:
                try:
                    roles = api.keystone.roles_for_user(self.request,
                                                        user.id,
                                                        project_id)
                except Exception:
                    exceptions.handle(request,
                                      err_msg,
                                      redirect=reverse(INDEX_URL))
                for role in roles:
                    field_name = self.get_member_field_name(role.id)
                    self.fields[field_name].initial.append(user.id)

    class Meta:
        name = _("Project Members")
        slug = PROJECT_USER_MEMBER_SLUG


class UpdateProjectMembers(workflows.UpdateMembersStep):
    action_class = UpdateProjectMembersAction
    available_list_title = _("All Users")
    members_list_title = _("Project Members")
    no_available_text = _("No users found.")
    no_members_text = _("No users.")

    def contribute(self, data, context):
        if data:
            try:
                roles = api.keystone.role_list(self.workflow.request)
            except Exception:
                exceptions.handle(self.workflow.request,
                                  _('Unable to retrieve user list.'))

            post = self.workflow.request.POST
            for role in roles:
                field = self.get_member_field_name(role.id)
                context[field] = post.getlist(field)
        return context


class UpdateProjectGroupsAction(workflows.MembershipAction):
    def __init__(self, request, *args, **kwargs):
        super(UpdateProjectGroupsAction, self).__init__(request,
                                                        *args,
                                                        **kwargs)
        err_msg = _('Unable to retrieve group list. Please try again later.')
        # Use the domain_id from the project
        domain_id = self.initial.get("domain_id", None)
        project_id = ''
        if 'project_id' in self.initial:
            project_id = self.initial['project_id']

        # Get the default role
        try:
            default_role = api.keystone.get_default_role(self.request)
            # Default role is necessary to add members to a project
            if default_role is None:
                default = getattr(settings,
                                  "OPENSTACK_KEYSTONE_DEFAULT_ROLE", None)
                msg = _('Could not find default role "%s" in Keystone') % \
                        default
                raise exceptions.NotFound(msg)
        except Exception:
            exceptions.handle(self.request,
                              err_msg,
                              redirect=reverse(INDEX_URL))
        default_role_name = self.get_default_role_field_name()
        self.fields[default_role_name] = forms.CharField(required=False)
        self.fields[default_role_name].initial = default_role.id

        # Get list of available groups
        all_groups = []
        try:
            all_groups = api.keystone.group_list(request,
                                                 domain=domain_id)
        except Exception:
            exceptions.handle(request, err_msg)
        groups_list = [(group.id, group.name) for group in all_groups]

        # Get list of roles
        role_list = []
        try:
            role_list = api.keystone.role_list(request)
        except Exception:
            exceptions.handle(request,
                              err_msg,
                              redirect=reverse(INDEX_URL))
        for role in role_list:
            field_name = self.get_member_field_name(role.id)
            label = role.name
            self.fields[field_name] = forms.MultipleChoiceField(required=False,
                                                                label=label)
            self.fields[field_name].choices = groups_list
            self.fields[field_name].initial = []

        # Figure out groups & roles
        if project_id:
            for group in all_groups:
                try:
                    roles = api.keystone.roles_for_group(self.request,
                                                         group=group.id,
                                                         project=project_id)
                except Exception:
                    exceptions.handle(request,
                                      err_msg,
                                      redirect=reverse(INDEX_URL))
                for role in roles:
                    field_name = self.get_member_field_name(role.id)
                    self.fields[field_name].initial.append(group.id)

    class Meta:
        name = _("Project Groups")
        slug = PROJECT_GROUP_MEMBER_SLUG


class UpdateProjectGroups(workflows.UpdateMembersStep):
    action_class = UpdateProjectGroupsAction
    available_list_title = _("All Groups")
    members_list_title = _("Project Groups")
    no_available_text = _("No groups found.")
    no_members_text = _("No groups.")

    def contribute(self, data, context):
        if data:
            try:
                roles = api.keystone.role_list(self.workflow.request)
            except Exception:
                exceptions.handle(self.workflow.request,
                                  _('Unable to retrieve role list.'))

            post = self.workflow.request.POST
            for role in roles:
                field = self.get_member_field_name(role.id)
                context[field] = post.getlist(field)
        return context


class CreateProject(workflows.Workflow):
    slug = "create_project"
    name = _("Create Project")
    finalize_button_name = _("Create Project")
    success_message = _('Created new project "%s".')
    failure_message = _('Unable to create project "%s".')
    success_url = "horizon:admin:projects:index"
    default_steps = (CreateProjectInfo,
                     UpdateProjectMembers,
                     # jt
                     #UpdateProjectQuota
                     UpdateProjectQuota,
                     UpdateDAIR)

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):
        if PROJECT_GROUP_ENABLED:
            self.default_steps = (CreateProjectInfo,
                                  UpdateProjectMembers,
                                  UpdateProjectGroups,
                                  # jt
                                  #UpdateProjectQuota)
                                  UpdateProjectQuota,
                                  UpdateDAIR)
        super(CreateProject, self).__init__(request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)

    def format_status_message(self, message):
        return message % self.context.get('name', 'unknown project')

    def handle(self, request, data):
        # create the project
        domain_id = data['domain_id']
        try:
            desc = data['description']
            self.object = api.keystone.tenant_create(request,
                                                     name=data['name'],
                                                     description=desc,
                                                     enabled=data['enabled'],
                                                     domain=domain_id)
        except Exception:
            exceptions.handle(request, ignore=True)
            return False

        project_id = self.object.id

        # update project members
        users_to_add = 0
        try:
            available_roles = api.keystone.role_list(request)
            member_step = self.get_step(PROJECT_USER_MEMBER_SLUG)
            # count how many users are to be added
            for role in available_roles:
                field_name = member_step.get_member_field_name(role.id)
                role_list = data[field_name]
                users_to_add += len(role_list)
            # add new users to project
            for role in available_roles:
                field_name = member_step.get_member_field_name(role.id)
                role_list = data[field_name]
                users_added = 0
                for user in role_list:
                    api.keystone.add_tenant_user_role(request,
                                                      project=project_id,
                                                      user=user,
                                                      role=role.id)
                    users_added += 1
                users_to_add -= users_added

            # jt
            # Make sure admin is added to the project as a ResellerAdmin
            users = api.keystone.user_list(request)
            admin_id = [user.id for user in users if user.name == 'admin'][0]
            reseller_admin_role_id = [role.id for role in available_roles if role.name == 'ResellerAdmin'][0]
            api.keystone.add_tenant_user_role(request,
                                              project=project_id,
                                              user=admin_id,
                                              role=reseller_admin_role_id)

        except Exception:
            if PROJECT_GROUP_ENABLED:
                group_msg = _(", add project groups")
            else:
                group_msg = ""
            exceptions.handle(request, _('Failed to add %(users_to_add)s '
                                         'project members%(group_msg)s and '
                                         'set project quotas.')
                                      % {'users_to_add': users_to_add,
                                         'group_msg': group_msg})

        if PROJECT_GROUP_ENABLED:
            # update project groups
            groups_to_add = 0
            try:
                available_roles = api.keystone.role_list(request)
                member_step = self.get_step(PROJECT_GROUP_MEMBER_SLUG)

                # count how many groups are to be added
                for role in available_roles:
                    field_name = member_step.get_member_field_name(role.id)
                    role_list = data[field_name]
                    groups_to_add += len(role_list)
                # add new groups to project
                for role in available_roles:
                    field_name = member_step.get_member_field_name(role.id)
                    role_list = data[field_name]
                    groups_added = 0
                    for group in role_list:
                        api.keystone.add_group_role(request,
                                                    role=role.id,
                                                    group=group,
                                                    project=project_id)
                        groups_added += 1
                    groups_to_add -= groups_added
            except Exception:
                exceptions.handle(request, _('Failed to add %s project groups '
                                             'and update project quotas.'
                                             % groups_to_add))

        # Update the project quota.
        nova_data = dict(
            [(key, data[key]) for key in quotas.NOVA_QUOTA_FIELDS])
        try:
            nova.tenant_quota_update(request, project_id, **nova_data)

            if base.is_service_enabled(request, 'volume'):
                cinder_data = dict([(key, data[key]) for key in
                                    quotas.CINDER_QUOTA_FIELDS])
                cinder.tenant_quota_update(request,
                                           project_id,
                                           **cinder_data)

            if api.base.is_service_enabled(request, 'network') and \
                    api.neutron.is_quotas_extension_supported(request):
                neutron_data = dict([(key, data[key]) for key in
                                     quotas.NEUTRON_QUOTA_FIELDS])
                api.neutron.tenant_quota_update(request,
                                                project_id,
                                                **neutron_data)
            # jt
            if data['images'] != 5:
                api.jt.set_image_quota(project_id, data['images'])
            if data['expiration'] != 'Information not available.':
                api.jt.set_expiration_date(project_id, data['expiration'])
            if data['start_date'] != 'Information not available.':
                api.jt.set_start_date(project_id, data['start_date'])
            if data['dair_notice'] != '':
                api.jt.set_dair_notice(project_id, data['dair_notice'])
            if data['dair_notice_link'] != '':
                api.jt.set_dair_notice_link(project_id, data['dair_notice_link'])
            if data['object_mb'] != 204800:
                api.jt.set_object_mb_quota(project_id, data['object_mb'])
            if data['reseller_logo'] != 'Information not available.':
                api.jt.set_reseller_logo(project_id, data['reseller_logo'])
            #tm
            if data['research_participant'] != '':
                api.jt.set_research_participant(project_id, data['research_participant'])
        except Exception:
            exceptions.handle(request, _('Unable to set project quotas.'))
        return True


class UpdateProjectInfoAction(CreateProjectInfoAction):
    enabled = forms.BooleanField(required=False, label=_("Enabled"))

    class Meta:
        name = _("Project Info")
        slug = 'update_info'
        help_text = _("From here you can edit the project details.")


class UpdateProjectInfo(workflows.Step):
    action_class = UpdateProjectInfoAction
    depends_on = ("project_id",)
    contributes = ("domain_id",
                   "domain_name",
                   "name",
                   "description",
                   "enabled")


class UpdateProject(workflows.Workflow):
    slug = "update_project"
    name = _("Edit Project")
    finalize_button_name = _("Save")
    success_message = _('Modified project "%s".')
    failure_message = _('Unable to modify project "%s".')
    success_url = "horizon:admin:projects:index"
    default_steps = (UpdateProjectInfo,
                     UpdateProjectMembers,
                     # jt
                     #UpdateProjectQuota)
                     UpdateProjectQuota,
                     UpdateDAIR)

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):
        if PROJECT_GROUP_ENABLED:
            self.default_steps = (UpdateProjectInfo,
                                  UpdateProjectMembers,
                                  UpdateProjectGroups,
                                  # jt
                                  #UpdateProjectQuota)
                                  UpdateProjectQuota,
                                  UpdateDAIR)

        super(UpdateProject, self).__init__(request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)

    def format_status_message(self, message):
        return message % self.context.get('name', 'unknown project')

    def handle(self, request, data):
        # FIXME(gabriel): This should be refactored to use Python's built-in
        # sets and do this all in a single "roles to add" and "roles to remove"
        # pass instead of the multi-pass thing happening now.

        project_id = data['project_id']
        domain_id = ''
        # update project info
        try:
            project = api.keystone.tenant_update(
                request,
                project_id,
                name=data['name'],
                description=data['description'],
                enabled=data['enabled'])
            # Use the domain_id from the project if available
            domain_id = getattr(project, "domain_id", None)
        except Exception:
            exceptions.handle(request, ignore=True)
            return False

        # update project members
        users_to_modify = 0
        # Project-user member step
        member_step = self.get_step(PROJECT_USER_MEMBER_SLUG)
        try:
            # Get our role options
            available_roles = api.keystone.role_list(request)
            # Get the users currently associated with this project so we
            # can diff against it.
            project_members = api.keystone.user_list(request,
                                                     project=project_id)
            users_to_modify = len(project_members)

            for user in project_members:
                # Check if there have been any changes in the roles of
                # Existing project members.
                current_roles = api.keystone.roles_for_user(self.request,
                                                            user.id,
                                                            project_id)
                current_role_ids = [role.id for role in current_roles]

                for role in available_roles:
                    field_name = member_step.get_member_field_name(role.id)
                    # Check if the user is in the list of users with this role.
                    if user.id in data[field_name]:
                        # Add it if necessary
                        if role.id not in current_role_ids:
                            # user role has changed
                            api.keystone.add_tenant_user_role(
                                request,
                                project=project_id,
                                user=user.id,
                                role=role.id)
                        else:
                            # User role is unchanged, so remove it from the
                            # remaining roles list to avoid removing it later.
                            index = current_role_ids.index(role.id)
                            current_role_ids.pop(index)

                # Prevent admins from doing stupid things to themselves.
                is_current_user = user.id == request.user.id
                is_current_project = project_id == request.user.tenant_id
                admin_roles = [role for role in current_roles
                               if role.name.lower() == 'admin']
                if len(admin_roles):
                    removing_admin = any([role.id in current_role_ids
                                          for role in admin_roles])
                else:
                    removing_admin = False
                if is_current_user and is_current_project and removing_admin:
                    # Cannot remove "admin" role on current(admin) project
                    msg = _('You cannot revoke your administrative privileges '
                            'from the project you are currently logged into. '
                            'Please switch to another project with '
                            'administrative privileges or remove the '
                            'administrative role manually via the CLI.')
                    messages.warning(request, msg)

                # Otherwise go through and revoke any removed roles.
                else:
                    for id_to_delete in current_role_ids:
                        api.keystone.remove_tenant_user_role(
                            request,
                            project=project_id,
                            user=user.id,
                            role=id_to_delete)
                users_to_modify -= 1

            # Grant new roles on the project.
            for role in available_roles:
                field_name = member_step.get_member_field_name(role.id)
                # Count how many users may be added for exception handling.
                users_to_modify += len(data[field_name])
            for role in available_roles:
                users_added = 0
                field_name = member_step.get_member_field_name(role.id)
                for user_id in data[field_name]:
                    if not filter(lambda x: user_id == x.id, project_members):
                        api.keystone.add_tenant_user_role(request,
                                                          project=project_id,
                                                          user=user_id,
                                                          role=role.id)
                    users_added += 1
                users_to_modify -= users_added
        except Exception:
            if PROJECT_GROUP_ENABLED:
                group_msg = _(", update project groups")
            else:
                group_msg = ""
            exceptions.handle(request, _('Failed to modify %(users_to_modify)s'
                                         ' project members%(group_msg)s and '
                                         'update project quotas.')
                                       % {'users_to_modify': users_to_modify,
                                          'group_msg': group_msg})
            return True

        if PROJECT_GROUP_ENABLED:
            # update project groups
            groups_to_modify = 0
            member_step = self.get_step(PROJECT_GROUP_MEMBER_SLUG)
            try:
                # Get the groups currently associated with this project so we
                # can diff against it.
                project_groups = api.keystone.group_list(request,
                                                         domain=domain_id,
                                                         project=project_id)
                groups_to_modify = len(project_groups)
                for group in project_groups:
                    # Check if there have been any changes in the roles of
                    # Existing project members.
                    current_roles = api.keystone.roles_for_group(
                        self.request,
                        group=group.id,
                        project=project_id)
                    current_role_ids = [role.id for role in current_roles]
                    for role in available_roles:
                        # Check if the group is in the list of groups with
                        # this role.
                        field_name = member_step.get_member_field_name(role.id)
                        if group.id in data[field_name]:
                            # Add it if necessary
                            if role.id not in current_role_ids:
                                # group role has changed
                                api.keystone.add_group_role(
                                    request,
                                    role=role.id,
                                    group=group.id,
                                    project=project_id)
                            else:
                                # Group role is unchanged, so remove it from
                                # the remaining roles list to avoid removing it
                                # later.
                                index = current_role_ids.index(role.id)
                                current_role_ids.pop(index)

                    # Revoke any removed roles.
                    for id_to_delete in current_role_ids:
                        api.keystone.remove_group_role(request,
                                                       role=id_to_delete,
                                                       group=group.id,
                                                       project=project_id)
                    groups_to_modify -= 1

                # Grant new roles on the project.
                for role in available_roles:
                    field_name = member_step.get_member_field_name(role.id)
                    # Count how many groups may be added for error handling.
                    groups_to_modify += len(data[field_name])
                for role in available_roles:
                    groups_added = 0
                    field_name = member_step.get_member_field_name(role.id)
                    for group_id in data[field_name]:
                        if not filter(lambda x: group_id == x.id,
                                      project_groups):
                            api.keystone.add_group_role(request,
                                                        role=role.id,
                                                        group=group_id,
                                                        project=project_id)
                        groups_added += 1
                    groups_to_modify -= groups_added
            except Exception:
                exceptions.handle(request, _('Failed to modify %s project '
                                             'members, update project groups '
                                             'and update project quotas.'
                                             % groups_to_modify))
                return True

        # update the project quota
        nova_data = dict(
            [(key, data[key]) for key in quotas.NOVA_QUOTA_FIELDS])
        try:
            nova.tenant_quota_update(request,
                                     project_id,
                                     **nova_data)

            if base.is_service_enabled(request, 'volume'):
                cinder_data = dict([(key, data[key]) for key in
                                    quotas.CINDER_QUOTA_FIELDS])
                cinder.tenant_quota_update(request,
                                           project_id,
                                           **cinder_data)

            if api.base.is_service_enabled(request, 'network') and \
                    api.neutron.is_quotas_extension_supported(request):
                neutron_data = dict([(key, data[key]) for key in
                                     quotas.NEUTRON_QUOTA_FIELDS])
                api.neutron.tenant_quota_update(request,
                                                project_id,
                                                **neutron_data)
            # jt
            # MJ
            # Unfortunately these quotas values are always written when quotas are
            # changed as we don't have access to the pre-existing values.
            api.jt.set_image_quota(project_id, data['images'])
            api.jt.set_expiration_date(project_id, data['expiration'])
            api.jt.set_start_date(project_id, data['start_date'])
            api.jt.set_object_mb_quota(project_id, data['object_mb'])
            api.jt.set_reseller_logo(project_id, data['reseller_logo'])
            #tm
            api.jt.set_research_participant(project_id, data['research_participant'])

            is_admin_notice = False
            admin_tenant_id = get_admin_tenant_id(request)
            if admin_tenant_id == project_id:
                is_admin_notice = True
            api.jt.set_dair_notice(project_id, data['dair_notice'], is_admin_notice)
            api.jt.set_dair_notice_link(project_id, data['dair_notice_link'], is_admin_notice)

            return True
        except Exception:
            exceptions.handle(request, _('Modified project information and '
                                         'members, but unable to modify '
                                         'project quotas.'))
            return True
