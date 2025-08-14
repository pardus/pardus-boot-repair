#!/usr/bin/env python3
import sys
import os
import re
import gi
import subprocess
import gettext
gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Handy, Gdk, Gio, GLib, Vte

gettext.install("pardus-boot-repair", "/usr/share/locale/")
Handy.init()

APPVERSION = "1.0.1"
APP_DIR = os.path.dirname(os.path.realpath(__file__))

resource = Gio.resource_load(
    APP_DIR + "/data/tr.org.pardus.boot-repair.gresource")
Gio.Resource._register(resource)


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="tr.org.pardus.boot-repair",
            **kwargs
        )

        # main
        self.builder = Gtk.Builder()
        self.builder.add_from_resource(
            "/tr/org/pardus/boot-repair/ui/AppWindow.ui")
        self.builder.connect_signals(self)
        self.window = self.builder.get_object("window_main")
        self.deck = self.builder.get_object("deck_main")

        # pages
        self.page_main = self.builder.get_object("box_page_main")
        self.page_questions = self.builder.get_object("box_page_questions")
        self.page_advanced = self.builder.get_object("box_page_advanced")
        self.page_loading = self.builder.get_object("box_page_loading")

        # questions page
        self.carousel_questions = self.builder.get_object("carousel_questions")
        self.button_questions_mainpage = self.builder.get_object(
            "button_mainpage1")
        self.button_questions_continue = self.builder.get_object(
            "button_questions_continue")
        self.titlebar_page_questions = self.builder.get_object(
            "titlebar_page_questions")

        # loading page
        self.btn_go_mainpage = self.builder.get_object(
            "button_loading_to_mainpage")
        self.btn_close_logs = self.builder.get_object("button_close_logs")
        self.btn_show_log = self.builder.get_object("button_show_log")
        self.btn_copy_logs = self.builder.get_object("button_copy_logs")
        self.status_page = self.builder.get_object("page_status")
        self.spinner_loading = self.builder.get_object("spinner_page_loading")
        self.box_vte = self.builder.get_object("box_vte")

        # Vte Terminal
        self.vte_terminal = Vte.Terminal()
        self.vte_terminal.set_hexpand(True)
        self.vte_terminal.set_vexpand(True)
        self.box_vte.add(self.vte_terminal)
        self.vte_terminal.show()
        self.vte_terminal.connect("child-exited", self.vte_exited)
        style_context = self.window.get_style_context()
        background_color= style_context.get_background_color(Gtk.StateFlags.NORMAL);
        foreground_color= style_context.get_color(Gtk.StateFlags.NORMAL);
        self.vte_terminal.set_color_background(background_color)
        self.vte_terminal.set_color_foreground(foreground_color)

        self.dialog_about = self.builder.get_object("dialog_about")
        self.dialog_about.set_version(APPVERSION)
        self.button_about = self.builder.get_object("button_about")

    def do_activate(self):
        self.window.set_application(self)
        self.window.present()

    def on_window_destroy_event(self, widget, event):
        if self.deck.get_visible_child() == self.page_loading and self.spinner_loading.get_property("active") == True:
            dialog = Gtk.MessageDialog(
                parent=self.window,
                modal=True,
                destroy_with_parent=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=_("You can't close the application while an operation is in progress. Please wait until the operation is completed.")
            )
            dialog.run()
            dialog.destroy()
            # return True will prevent the window from closing
            return True
        # This will allow the window to close
        return

    def on_button_mainpage_clicked(self, widget):
        self.deck.set_visible_child(self.page_main)

    def on_button_show_log_clicked(self, widget):
        self.box_vte.set_visible(True)
        self.status_page.set_visible(False)
        self.btn_go_mainpage.set_visible(False)
        self.btn_show_log.set_visible(False)
        self.btn_close_logs.set_visible(True)
        self.btn_copy_logs.set_visible(True)

    def on_button_close_logs_clicked(self, widget):
        self.box_vte.set_visible(False)
        self.status_page.set_visible(True)
        self.btn_go_mainpage.set_visible(True)
        self.btn_show_log.set_visible(True)
        self.btn_close_logs.set_visible(False)
        self.btn_copy_logs.set_visible(False)

    def on_button_copy_logs_clicked(self, widget):
        alltext, attrlist = self.vte_terminal.get_text_range(
            0, 0, self.vte_terminal.get_scrollback_lines(), self.vte_terminal.get_column_count())

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(alltext.strip(), -1)
        clipboard.store()

    def on_row_advanced_options_activated(self, widget):
        self.deck.set_visible_child(self.page_advanced)

    def on_button_about_clicked(self, widget):
        self.dialog_about.run()
        self.dialog_about.hide()

    """
        row functions are seperated to at least 2 subfunctions
        pre() and post()
        pre() function will be called first and it will prepare the page for the user input or execute the command then set the post_command to the post() function
        post_command is a function that will be called after the vte command is executed (see vte_cb() function)
        post() function will be called after the command is executed, it will update the status page and do the necessary actions
    """
    """
        get_user, get_rootfs, get_mbr functions are used to get the user, rootfs and mbr (will try to get automatically if there is only one)
        if there is no user, rootfs or mbr, it will show an error message
        if there is only one user, rootfs or mbr, it will set self.user, self.rootfs or self.mbr to it
        if there is more than one user, rootfs or mbr, the function will return None but it will create a listbox page for the user to select one of them
        after the user selects one of them, the get_user, get_rootfs or get_mbr function will call the row function again (see pending_func)
    """
    """
        row_init_func is a function should be called before the row pre function.
    """

    def row_init_func(self, pre_function):
        self.deck.set_visible_child(self.page_loading)
        self.update_status_page(_("Processing your request."), "content-loading-symbolic", _(
            "We will ask you some questions after we process your request."), False, False)
        pre_function()

    def on_row_reinstall_grub_activated(self, widget):
        def pre():
            if self.get_rootfs(widget, pre) == None or self.get_mbr(widget, pre) == None:
                return

            if os.path.exists("/sys/firmware/efi/efivars"):
                clear_efi = self.ask_confirmation(_(
                    "Do you want to clear efivars?"))
            else:
                clear_efi = 'n'

            removable= self.ask_confirmation(
                _("On some systems, the BIOS may not detect grub until installed as a removable device. Do you want to install grub as a removable device? You should only say yes if you cannot boot into the system after installation."))

            self.update_status_page(_("Reinstalling GRUB Bootloader"), "content-loading-symbolic", _(
                "We're reinstalling the GRUB boot loader to ensure your system can start up properly. This process may take a few moments. Once complete, your computer should boot into Pardus as usual."), False, False)

            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} mbr={} clear_efi={} removable={} grub-reinstall".format(
                    self.rootfs.name, self.mbr, clear_efi, removable), post)
            else:
                self.vte_command("env subvolume={} disk={} mbr={} clear_efi={} removable={} grub-reinstall".format(
                    self.rootfs.root_subvol, self.rootfs.name, self.mbr, clear_efi, removable), post)

        def post():
            self.update_status_page(_("GRUB Successfully Reinstalled"), "emblem-ok-symbolic", _(
                "Great news! The GRUB boot loader has been successfully reinstalled on your system. You're all set to restart your computer and resume normal operation."), True, True)

        self.row_init_func(pre)

    def on_row_fix_broken_activated(self, widget):
        def pre():
            if self.get_rootfs(widget, pre) == None:
                return

            self.update_status_page(_("Fixing Broken Packages"), "content-loading-symbolic", _(
                "We're resolving issues with broken packages on your system to ensure everything works. This may take some time, but we're on it. Once complete, your system should be stable and ready for use."), False, False)

            if self.rootfs.root_subvol == None:
                self.vte_command(
                    "env disk={} fix-broken-packages".format(self.rootfs.name), post)
            else:
                self.vte_command("env subvolume={} disk={} fix-broken-packages".format(
                    self.rootfs.root_subvol, self.rootfs.name), post)

        def post():
            self.update_status_page(_("Packages Repaired"), "emblem-ok-symbolic", _(
                "Great news! The broken packages on your system have been successfully repaired."), True, True)

        self.row_init_func(pre)

    def on_row_reset_password_activated(self, widget):
        def pre():
            if self.get_rootfs(widget, pre) == None or self.get_user(widget, pre) == None:
                return None

            self.password_page = self.new_page_input(
                _("Enter new password"), after_userdata)

        def after_userdata(*args, **kwargs):
            password1 = self.password_page.entry.get_text()
            password2 = self.password_page.entry_second.get_text()

            self.update_status_page(_("Resetting password"), "content-loading-symbolic", _(
                "We're resetting your password to provide access to your account. This process will only take a moment. Once complete, you'll be able to log in with your new password into your Pardus system."), False, False)

            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} user={} pass1={} pass2={} reset-password".format(
                    self.rootfs.name, self.user, password1, password2), post, False)
            else:
                self.vte_command("env subvolume={} user={} disk={} pass1={} pass2={} reset-password".format(
                    self.rootfs.root_subvol, self.user, self.rootfs.name, password1, password2), post, False)

        def post():
            self.update_status_page(_("Password Reset Completed"), "emblem-ok-symbolic", _(
                "Your password has been successfully reset. You can now log in to your account with the new password."), True, True)

        self.row_init_func(pre)

    def on_row_update_activated(self, widget):
        def pre():
            if self.get_rootfs(widget, pre) == None:
                return

            self.update_status_page(_("Updating Software Packages"), "content-loading-symbolic", _(
                "We're currently updating the software packages on your system to ensure you have the latest features and security enhancements. This process may take some time depending on the number of updates available. Please be patient."), False, False)

            if self.rootfs.root_subvol == None:
                self.vte_command(
                    "env disk={} full-upgrade".format(self.rootfs.name), post)
            else:
                self.vte_command("env subvolume={} disk={} full-upgrade".format(
                    self.rootfs.root_subvol, self.rootfs.name), post)

        def post():
            self.update_status_page(_("Software Packages Updated"), "emblem-ok-symbolic", _(
                "Your system's software packages have been successfully updated. You now have the latest features and security patches installed."), True, True)

        self.row_init_func(pre)

    def on_row_reinstall_activated(self, widget):
        def pre():
            if self.get_rootfs(widget, pre) == None or self.get_mbr(widget, pre) == None:
                return

            self.update_status_page(_("System Reinstallation"), "content-loading-symbolic", _(
                "We're performing a clean reinstall of your system to ensure a fresh start. This process will reset your system to its original state, removing all applications."), False, False)

            if self.rootfs.root_subvol == None:
                self.vte_command(
                    "env disk={} mbr={} pardus-reinstall".format(self.rootfs.name, self.mbr), post)
            else:
                self.vte_command("env subvolume={} disk={} mbr={} pardus-reinstall".format(
                    self.rootfs.root_subvol, self.rootfs.name, self.mbr), post)

        def post():
            self.update_status_page(_("System Reinstallation Completed"), "emblem-ok-symbolic", _(
                "Your system has been successfully reinstalled. Everything is now fresh and ready for you."), True, True)

        self.row_init_func(pre)

    def on_row_repair_filesystem_activated(self, widget):
        def pre():
            self.update_status_page(_("Detecting Partitions"), "content-loading-symbolic", _(
                "We're scanning your system to locate available partitions."), False, False)

            self.partitions = self.list_partitions()
            if len(self.partitions) == 0:
                self.update_status_page(_("Unable to Detect Partitions"), "dialog-error-symbolic", _(
                    "We couldn't find any partitions on your system. This could indicate a problem with your disk or partition table. Please double-check your disk connections and configuration."), True, True)
                return

            partition_names = [part.name for part in self.partitions]
            partition_os = [part.operating_system for part in self.partitions]

            self.repair_page = self.new_page_listbox(
                _("Choose Partition for Filesystem Repair"), partition_names, partition_os, after_userdata)

        def after_userdata(widget=None, userdata=None, partition=None):
            if partition == None:
                selected = self.repair_page.listbox.get_selected_row().get_title()
                part = next((x for x in self.partitions if x.name == selected), None)
                return process_partition(after_userdata, part)
            else:
                part = partition

            self.update_status_page(_("Repairing Filesystem on {}").format(part.path), "content-loading-symbolic", _(
                "We're currently repairing the filesystem on the selected partition. This process may take some time, depending on the size and severity of the issues found. Please be patient while we work to restore the partition's functionality."), False, False)
            self.vte_command(
                "env disk={} check-filesystem".format(part.name), post)

        def post():
            self.update_status_page(_("Filesystem Repair Successful"), "emblem-ok-symbolic", _(
                "The filesystem has been successfully repaired. Your data should now be accessible without any issues."), True, True)

        def process_partition(pending_func, part):
            if part.is_luks:
                self.unlock_luks(part, process_partition, pending_func)
                return None
            if part.is_lvm:
                self.mount_lvm(part, process_partition, pending_func)
                return None

            if pending_func != None:
                pending_func(None, None, part)

        self.row_init_func(pre)

    def on_row_reset_config_activated(self, widget):
        def pre():
            if self.get_rootfs(widget, pre) == None or self.get_user(widget, pre) == None:
                return

            self.update_status_page(_("Resetting User Settings"), "content-loading-symbolic", _(
                "We're resetting your user configuration to its default state. This will revert any custom settings back to their original values. Please note that any personalized preferences will be lost. Once complete, your system will be refreshed and ready for use."), False, False)

            if self.rootfs.root_subvol == None:
                self.vte_command(
                    "env pardus-chroot /dev/{} su {} -c 'cd ; rm -rvf .dbus .cache .local .config'".format(self.rootfs.name, self.user), post)
            else:
                self.vte_command("env subvolume={} pardus-chroot /dev/{} su {} -c 'cd ; rm -rvf .dbus .cache .local .config'".format(
                    self.rootfs.root_subvol, self.rootfs.name, self.user), post)

        def post():
            self.update_status_page(_("Configuration Reset Completed"), "emblem-ok-symbolic", _(
                "Great news! Your user configuration has been successfully reset to its default settings."), True, True)

        self.row_init_func(pre)

    def on_row_dump_log_activated(self, widget):
        def pre():
            if self.get_rootfs(widget, pre) == None:
                return

            liveuser_home = self.run_command(
                'grep "x:1000:" /etc/passwd | cut -f 6 -d ":"')
            self.update_status_page(_("Extracting System Logs"), "content-loading-symbolic", _(
                "We're collecting important system logs and placing them in the '{}' directory as you requested. These logs contain helpful information about your system's activity and any issues it may be experiencing. Depending on how much information there is, this might take a little time. Thanks for waiting while we gather this data.").format(liveuser_home), False, False)

            if self.rootfs.root_subvol == None:
                self.vte_command(
                    "env disk={} dump-info-log {}".format(self.rootfs.name, liveuser_home), post, False)
            else:
                self.vte_command("env subvolume={} disk={} dump-info-log {}".format(
                    self.rootfs.root_subvol, self.rootfs.name, liveuser_home), post, False)

        def post():
            self.update_status_page(_("System Logs Extracted"), "emblem-ok-symbolic", _(
                "Great news! The system logs have been successfully extracted. This valuable information can help diagnose any issues with your system."), True, True)

        self.row_init_func(pre)

    def on_row_chroot_activated(self, widget):
        def pre():
            self.update_status_page(_("Entering Chroot Environment"), "content-loading-symbolic", _(
                "We're accessing a special system environment called chroot at your request. This allows you to make changes as if you were working directly on your installed operating system. Please wait while we set up this environment to address your needs."), False, True)
            if self.get_rootfs(widget, pre) == None or self.get_user(widget, pre) == None:
                return

            # show terminal page
            self.btn_show_log.clicked()
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} pardus-chroot /dev/{} su {} -".format(
                    self.rootfs.name, self.rootfs.name, self.user), post, False)
            else:
                self.vte_command("env subvolume={} pardus-chroot /dev/{} su {} -".format(
                    self.rootfs.root_subvol, self.rootfs.name, self.user), post, False)
            self.user = None

        def post():
            self.update_status_page(_("Chroot Process Successfully Concluded"), "emblem-ok-symbolic", _(
                "The chroot process has finished successfully"), True, True)

        self.row_init_func(pre)

    def update_status_page(self, title, icon_name, description, stop_spinner=False, enable_mainpage=True):
        self.status_page.set_title(title)
        self.status_page.set_icon_name(icon_name)
        self.status_page.set_description(description)
        self.btn_go_mainpage.set_sensitive(enable_mainpage)
        self.spinner_loading.start()
        self.btn_close_logs.clicked()
        if stop_spinner:
            self.spinner_loading.stop()

    def vte_command(self, command, post_func, ask_user_confirm=True):
        try:
            if ask_user_confirm and not self.ask_confirmation(_("Are you sure you want to continue? This action is irreversible and may cause data loss.")):
                self.update_status_page(_("Operation Cancelled"), "dialog-warning-symbolic", _(
                    "The operation has been cancelled by the user."), True, True)
                return
            env_vars = [f'{key}={value}' for key, value in os.environ.items()]
            exec = self.vte_terminal.spawn_async(
                Vte.PtyFlags.DEFAULT, os.environ['HOME'], ["/bin/bash", "-c", command], env_vars, GLib.SpawnFlags.SEARCH_PATH, None, None, -1, None, self.vte_cb)

            self.vte_terminal.disconnect_by_func(self.vte_exited)
            self.vte_terminal.connect(
                "child-exited", self.vte_exited, post_func)
        except Exception as e:
            # write error to stderr
            sys.stderr.write(str(e) + "\n")
            self.update_status_page(
                _("An error occured"), "dialog-error-symbolic", str(e), True, True)

    def vte_cb(self, Terminal, pid, error):
        Terminal.reset(True, True)
        if error != None or pid == -1:
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", _(
                "An error occurred before the command has been executed"), True, True)
            return

    def vte_exited(self, widget, status, post_func):
        exit_status = os.waitstatus_to_exitcode(status)
        if exit_status != 0:
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", _(
                "An error occured while executing the command. Please check the logs"), True, True)
            return
        if post_func == None:
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", _(
                "An error occurred after the command has been executed."), True, True)
            return
        post_func()

    def run_command(self, command: str, return_exitcode=False):
        try:
            proc = subprocess.Popen(
                ["/bin/bash", "-c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            output, err = proc.communicate()
            output = output.decode("utf-8").strip()
            exit_code = proc.returncode

            if return_exitcode:
                return output, exit_code
            return output
        except Exception as e:
            sys.stderr.write(str(e) + "\n")
            self.update_status_page(
                _("An error occured"), "dialog-error-symbolic", str(e), True, True)
            return None

    def get_rootfs(self, widget, pending_func):
        def pre():
            if hasattr(self, 'rootfs') and self.rootfs != None:
                return self.rootfs
            self.rootfs_list = self.detect_rootfs()
            if self.rootfs_list == None or len(self.rootfs_list) == 0:
                self.rootfs_list = self.list_partitions()
            if self.rootfs_list == None or len(self.rootfs_list) == 0:
                self.update_status_page(_("Root Filesystem Missing"), "dialog-error-symbolic", _(
                    "We couldn't locate the root filesystem on your system. This could be due to a disk failure, misconfiguration, or other issues. Please ensure that your disk is properly connected and configured."), True, True)
                return None
            elif len(self.rootfs_list) > 1:
                partition_names = [part.name for part in self.rootfs_list]
                partition_os = [
                    part.operating_system for part in self.rootfs_list]
                self.rootfs_page = self.new_page_listbox(
                    _("Select a root filesystem"), partition_names, partition_os, post, pending_func)
                return None
            process_partition(pending_func, self.rootfs_list[0])
            return None

        def post(widget, pending_func):
            selected = self.rootfs_page.listbox.get_selected_row().get_title()
            rootfs = next(
                (x for x in self.rootfs_list if x.name == selected), None)
            process_partition(pending_func, rootfs)

        def process_partition(pending_func, part):

            if part.is_luks:
                self.unlock_luks(part, process_partition, pending_func)
                return None
            if part.is_lvm:
                self.mount_lvm(part, process_partition, pending_func)
                return None

            part = self.check_if_rootfs(part)
            if part.is_rootfs:
                self.rootfs = part
            else:
                self.rootfs = None
            self.update_status_page(_("Root Filesystem Chosen"), "emblem-ok-symbolic", _(
                "You've selected the root filesystem for further action."), False, False)
            if pending_func != None:
                pending_func()

        return pre()

    def get_user(self, widget, pending_func):
        def pre():
            if not hasattr(self, 'user') or self.user == None:
                users = self.list_users(self.rootfs)
                if len(users) == 0:
                    self.update_status_page(_("No Users Detected"), "dialog-error-symbolic", _(
                        "We couldn't find any users on your system. This could indicate an issue with user accounts or system configuration. Please ensure that users are properly configured."), True, True)
                    return None
                elif len(users) > 1:
                    self.users_page = self.new_page_listbox(
                        _("Select a user"), users, None, after_userdata, pending_func)
                    return None
                self.user = users[0]
            return self.user

        def after_userdata(widget, pending_func):
            self.user = self.users_page.listbox.get_selected_row().get_title()
            self.update_status_page(_("User Chosen"), "emblem-ok-symbolic", _(
                "You've selected a user for further action. This step is important for making changes specific to the chosen user."), False, False)
            if pending_func != None:
                pending_func()
        return pre()

    def get_mbr(self, widget, pending_func):
        def pre():
            if not hasattr(self, 'mbr') or self.mbr == None:
                mbrs = self.list_mbrs()
                if len(mbrs) == 0:
                    self.update_status_page(_("Master Boot Record (MBR) Missing"), "dialog-error-symbolic", _(
                        "We couldn't locate the Master Boot Record (MBR) on your system. This critical component is necessary for booting your system. Please check your disk connections and configuration."), True, True)
                    return None
                elif len(mbrs) > 1:
                    self.mbr_page = self.new_page_listbox(
                        _("Select the Master Boot Record (MBR)"), mbrs, None, after_userdata, pending_func)
                    return None
                self.mbr = mbrs[0]
            return self.mbr

        def after_userdata(widget, pending_func):
            self.mbr = self.mbr_page.listbox.get_selected_row().get_title()
            self.update_status_page(_("MBR chosen"), "emblem-ok-symbolic", _(
                "You've successfully selected the Master Boot Record (MBR). This selection is essential for configuring your system's boot process."), False, False)
            if pending_func != None:
                pending_func()
        return pre()

    def ask_confirmation(self, msg_text):
        dialog = Gtk.MessageDialog(
            parent=self.window,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=msg_text
        )
        response = dialog.run()
        dialog.destroy()

        return response == Gtk.ResponseType.YES

    def get_operating_system(self, partitions):
        for part in partitions:
            part.operating_system = self.run_command(
                'env parts={} search-operating-system'.format(part.name)).split(":")[0].replace('"', '').strip()
        return partitions

    def detect_rootfs(self):
        rootfs = []
        partitions = self.list_partitions()
        self.update_status_page(_("Searching for Root Filesystem"), "content-loading-symbolic", _(
            "We're searching for the root filesystem on your system. This is essential for proper system operation. Please wait while we locate the root filesystem. Thank you for your patience."), False, False)
        for part in partitions:
            if part.mountpoint == "/":
                continue

            if part.fstype == "crypto_LUKS":
                prt_Types = self.run_command('lsblk -rno TYPE {}'.format(part.path)).strip().split()
                if len(prt_Types) > 1 and prt_Types[1] == "crypt":
                   part.name = self.run_command('lsblk -rno NAME {}'.format(part.path)).strip().split()[1]
                   part.path = "/dev/mapper/{}".format(part.name)
                   part.fstype = self.run_command('lsblk -rno FSTYPE {}'.format(part.path)).strip().split()[0]
                else:    
                    part.is_luks = True
                    rootfs.append(part)
                    continue

            if part.fstype == "LVM2_member":
                part.is_lvm = True
                rootfs.append(part)
                continue

            part = self.check_if_rootfs(part)
            if part.is_rootfs:
                rootfs.append(part)

        return rootfs

    def check_if_rootfs(self, part):
        TEMPDIR = self.run_command('mktemp -d')
        part.is_rootfs = False

        if part.mountpoint != "":
            self.run_command("umount -lf {}".format(part.mountpoint))

        self.run_command('mount {} {}'.format(part.path, TEMPDIR))
        if os.path.exists(TEMPDIR + "/var/lib/dpkg/"):
            part.is_rootfs = True

        if part.fstype == "btrfs" and not os.path.exists(TEMPDIR + "/etc/os-release"):
            subvol, part.is_rootfs = self.detect_btrfs_rootfs_subvolume(
                TEMPDIR)
            if subvol != None:
                part.root_subvol = subvol

        self.run_command('umount -l ' + TEMPDIR)
        self.run_command('rmdir ' + TEMPDIR)

        return part

    def detect_btrfs_rootfs_subvolume(self, mountdir):
        self.update_status_page(_("Searching for Btrfs Root Filesystem Subvolume"), "content-loading-symbolic", _(
            "We're searching for the Btrfs root filesystem subvolume on your system. This is essential for proper system operation. Please wait while we locate the Btrfs root filesystem subvolume. Thank you for your patience."), False, False)
        output = self.run_command(
            "btrfs subvolume list " + mountdir + " | awk '{print $9}'")
        for subvol in output.split("\n"):
            if os.path.exists("{}/{}/var/lib/dpkg/".format(mountdir, subvol)):
                is_rootfs = True
                return subvol, is_rootfs
        return None, False

    def unlock_luks(self, part, handler_func=None, pending_func= None):
        def pre():
            self.luks_page = self.new_page_input(
                _("Enter LUKS Password"), after_userdata, (part, handler_func, pending_func))
        
        def after_userdata(widget, userdata):
            password = self.luks_page.entry.get_text()
            part, handler_func, pending_func = userdata

            self.update_status_page(_("Unlocking Encrypted Device"), "content-loading-symbolic", _(
                "We're unlocking the encrypted device to access the data. This process may take a moment. Please wait while we unlock the device."), False, False)

            output, exit_code = self.run_command('echo {} | cryptsetup luksOpen {} luks-{}'.format(password, part.path, part.name), True)
            if exit_code != 0:
                dialog = Gtk.MessageDialog(
                    parent=self.window,
                    modal=True,
                    destroy_with_parent=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=_("An error occurred while unlocking the encrypted device. Please check the password and try again.")
                )                
                self.rootfs = None
                if pending_func != None:
                    pending_func()
                dialog.run()
                dialog.destroy()
                return

            part.path = "/dev/mapper/luks-{}".format(part.name)
            part.name = "/mapper/luks-{}".format(part.name)
            part.fstype = self.run_command('lsblk -no FSTYPE {}'.format(part.path)).strip()
            part.is_luks = False
            if part.fstype == "LVM2_member":
                part.is_lvm = True
                self.mount_lvm(part, handler_func, pending_func)
                return
            if part.fstype == "crypto_LUKS":
                return
            if handler_func != None:
                handler_func(pending_func, part)
            elif pending_func != None:
                pending_func()
        pre()

    def mount_lvm(self, part, handler_func=None, pending_func=None):
        def pre():
            vg_names = self.run_command(
                "pvs -o vg_name --noheadings --select pv_name={}".format(part.path)).split("\n")
            if len(vg_names) == 0:
                self.update_status_page(_("No Volume Groups Detected"), "dialog-error-symbolic", _(
                    "We couldn't find any volume groups on your system. This could indicate an issue with your LVM configuration. Please ensure that your LVM setup is correct."), True, True)
                return None
            elif len(vg_names) > 1:
                for vg in vg_names:
                    vg = vg.strip()
                self.vg_page = self.new_page_listbox(
                    _("Select a Volume Group"), vg_names, None, after_userdata, (part, handler_func, pending_func))
                return None
            after_userdata(None, (part, handler_func, pending_func), vg_names[0])

        def after_userdata(widget, userdata, vg_name=None):
            part, handler_func, pending_func = userdata
            if vg_name == None:
                vg_name = self.vg_page.listbox.get_selected_row().get_title()
            self.run_command("vgchange -ay {}".format(vg_name))

            LV_NAMES = []
            for lv in self.run_command("lvs -o lv_name --noheadings --select vg_name={}".format(vg_name)).split("\n"):
                lv = lv.strip()
                if lv == "":
                    continue
                LV_NAMES.append(lv)

            if len(LV_NAMES) == 0:
                self.update_status_page(_("No Logical Volumes Detected"), "dialog-error-symbolic", _(
                    "We couldn't find any logical volumes on your system. This could indicate an issue with your LVM configuration. Please ensure that your LVM setup is correct."), True, True)
                return None
            elif len(LV_NAMES) > 1:
                self.lv_page = self.new_page_listbox(
                    _("Select a Logical Volume"), LV_NAMES, None, after_lvm_selection, (vg_name, part, handler_func, pending_func))
                return None

            after_lvm_selection(None, (vg_name, part, handler_func, pending_func), LV_NAMES[0])

        def after_lvm_selection(widget, userdata, lv_name=None):
            vg_name, part, handler_func, pending_func = userdata
            if lv_name == None:
                lv_name = self.lv_page.listbox.get_selected_row().get_title()

            part.path = "/dev/{}/{}".format(vg_name, lv_name)
            part.name = "{}/{}".format(vg_name, lv_name)
            part.is_lvm = False


            if handler_func != None:
                handler_func(pending_func, part)
            elif pending_func != None:
                pending_func()
        pre()

    def list_partitions(self):
        partitions = []

        for block in os.listdir('/sys/block/'):
            if block.startswith(('loop', 'sr', 'zram')):
                continue

            if os.path.exists('/sys/block/{}/removable'.format(block)) and open('/sys/block/{}/removable'.format(block)).read().strip() == "1":
                continue

            for part in os.listdir('/sys/block/{}/'.format(block), ):
                if re.search(r'[0-9]$', part) == None:
                    continue

                partition = Partition()
                partition.name = part
                partition.path = "/dev/" + part
                for x in ["FSTYPE", "UUID", "SIZE", "LABEL", "MOUNTPOINT"]:
                    output = self.run_command(
                        'lsblk -rno {} {}'.format(x, partition.path)).split("\n")[0]
                    if output == None:
                        continue
                    partition.__setattr__(x.lower(), output.strip())
                    partition.is_luks = (partition.fstype == "crypto_LUKS")
                    partition.is_lvm = (partition.fstype == "LVM2_member")
         
                partitions.append(partition)

        partitions = self.get_operating_system(partitions)
        partitions.sort(key=lambda part: part.name)
        return partitions

    def list_users(self, rootfs):
        TEMPDIR = self.run_command('mktemp -d')
        if self.rootfs.root_subvol != None:
            self.run_command(
                "mount -o subvol={} /dev/{} {}".format(rootfs.root_subvol, rootfs.name, TEMPDIR))
        else:
            self.run_command("mount /dev/{} {}".format(rootfs.name, TEMPDIR))
        output = self.run_command(
            'grep -e ":x:[0-9][0-9][0-9][0-9]:" {}/etc/passwd | cut -f 1 -d ":"'.format(TEMPDIR))
        if output == "":
            return []
        self.run_command("umount -lf {}".format(TEMPDIR))
        users = output.split()
        users.append("root")
        return users

    def list_mbrs(self):
        entries = os.listdir('/sys/block/')
        mbrs = []
        for mbr in entries:
            if mbr.startswith(('loop', 'sr', 'zram')):
                continue
            try:
                with open('/sys/block/{}/size'.format(mbr)) as f:
                    size = int(f.read())
                    if size < 512:
                        continue
            except:
                continue
            mbrs.append(mbr)
        return mbrs

    def new_page_listbox(self, label_text, row_titles, row_subtitles, btn_next_clicked_signal, btn_next_userdata=None):
        page = Questions_page_listbox()
        self.titlebar_page_questions.set_title(label_text)
        self.button_questions_continue.set_sensitive(False)

        def on_questions_row_activated(widget):
            self.button_questions_continue.set_sensitive(True)

        def on_button_next_clicked(widget, userdata):
            self.deck.set_visible_child(self.page_loading,)
            btn_signal, btn_userdata = userdata
            btn_signal(widget, btn_userdata)
            self.button_questions_continue.disconnect_by_func(on_button_next_clicked)

        for child in self.carousel_questions.get_children():
            self.carousel_questions.remove(child)

        if row_subtitles == None or len(row_subtitles) == 0:
            row_subtitles = ["" for x in row_titles]
        elif len(row_titles) != len(row_subtitles):
            raise ValueError(
                "row_titles and row_subtitles must have the same length")

        self.button_questions_continue.connect(
            'clicked', on_button_next_clicked, (btn_next_clicked_signal, btn_next_userdata))
        for title, subtitle in zip(row_titles, row_subtitles):
            row = Handy.ActionRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_visible(True)
            row.get_style_context().add_class('activatable')
            row.set_property('activatable', True)
            row.connect("activated", on_questions_row_activated)
            page.listbox.insert(row, -1)

        self.carousel_questions.insert(page, -1)
        self.deck.set_visible_child(self.page_questions)
        return page

    def new_page_input(self, label_text, btn_continue_clicked_signal, btn_next_userdata=None):
        page = Questions_page_password_input()
        self.titlebar_page_questions.set_title(label_text)
        self.button_questions_continue.set_sensitive(False)

        for child in self.carousel_questions.get_children():
            self.carousel_questions.remove(child)

        def input_change_event(widget):
            entry_text = page.entry.get_text()
            entry_second_text = page.entry_second.get_text()
            if entry_text != entry_second_text and (entry_text != "" and entry_second_text != ""):
                page.warn_entry.set_visible(True)
                self.button_questions_continue.set_sensitive(False)
            if entry_text == entry_second_text and entry_text != "":
                page.warn_entry.set_visible(False)
                self.button_questions_continue.set_sensitive(True)
        
        def on_button_next_clicked(widget, userdata):
            self.deck.set_visible_child(self.page_loading,)
            btn_signal, btn_userdata = userdata
            btn_signal(widget, btn_userdata)
            self.button_questions_continue.disconnect_by_func(on_button_next_clicked)

        page.entry.connect("changed", input_change_event)
        page.entry_second.connect("changed", input_change_event)
        self.button_questions_continue.connect('clicked', on_button_next_clicked, (btn_continue_clicked_signal, btn_next_userdata))
        self.carousel_questions.insert(page, -1)
        self.deck.set_visible_child(self.page_questions)
        return page


class Page(Gtk.Box):
    def __init__(self):
        super().__init__()
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(15)
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_margin_start(15)
        self.set_margin_end(15)
        self.set_homogeneous(False)
        self.set_visible(True)
        self.set_vexpand(True)
        self.set_hexpand(True)


class Questions_page_listbox(Page):
    def __init__(self):
        super().__init__()

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.get_style_context().add_class('content')
        self.listbox.set_visible(True)
        self.listbox.set_vexpand(True)
        self.listbox.set_hexpand(True)
        self.add(self.listbox)



class Questions_page_password_input(Page):
    def __init__(self):
        super().__init__()

        self.entry = Gtk.Entry()
        self.entry.set_visible(True)
        self.entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.entry.set_visibility(False)
        self.entry.set_placeholder_text(_("Enter password"))
        self.add(self.entry)

        self.entry_second = Gtk.Entry()
        self.entry_second.set_visible(True)
        self.entry_second.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.entry_second.set_visibility(False)
        self.entry_second.set_placeholder_text(_("Re-enter password"))
        self.add(self.entry_second)

        self.warn_entry = Gtk.Label()
        self.warn_entry.set_text(_("Passwords do not match"))
        # set text color to red
        self.warn_entry.get_style_context().add_class('error')
        self.warn_entry.set_visible(False)
        self.add(self.warn_entry)


class Partition(object):
    def __init__(self):
        self.name = None
        self.path = None
        self.fstype = None
        self.uuid = None
        self.size = 0
        self.label = None
        self.is_rootfs = False
        self.root_subvol = None
        self.mountpoint = None
        self.operating_system = None
        self.is_luks = False
        self.is_lvm = False

if os.geteuid() != 0:        
        Gtk.MessageDialog(
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=_("This application requires root privileges to run. Please run it as root.")
        ).run()
        sys.exit(1)
    
app = Application()
app.run(sys.argv)
