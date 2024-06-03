#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
import gettext
gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")
gi.require_version("Vte", "2.91")
from threading import Thread
from gi.repository import Gtk, Handy, Gdk, Gio, GLib, Vte

gettext.install("pardus-boot-repair", "/usr/share/locale/")
Handy.init()

APPVERSION="0.5.2"
APP_DIR = os.path.dirname(os.path.realpath(__file__))

resource = Gio.resource_load(APP_DIR + "/data/tr.org.pardus.boot-repair.gresource")
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
        self.builder.add_from_resource("/tr/org/pardus/boot-repair/ui/AppWindow.ui")
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
        self.button_questions_mainpage = self.builder.get_object("button_mainpage1")

        # loading page
        self.btn_go_mainpage = self.builder.get_object("button_loading_to_mainpage")
        self.btn_close_logs = self.builder.get_object("button_close_logs")
        self.status_page = self.builder.get_object("page_status")
        self.spinner_loading = self.builder.get_object("spinner_page_loading")
        self.btn_show_log = self.builder.get_object("button_show_log")
        self.box_vte = self.builder.get_object("box_vte")

        # Vte Terminal
        self.vte_terminal = Vte.Terminal()
        self.vte_terminal.set_hexpand(True)
        self.vte_terminal.set_vexpand(True)
        self.box_vte.add(self.vte_terminal)
        self.vte_terminal.show()
        self.vte_terminal.connect("child-exited", self.vte_exited)
        self.post_command = None

        self.dialog_about = self.builder.get_object("dialog_about")
        self.dialog_about.set_version(APPVERSION)
        self.button_about = self.builder.get_object("button_about")

    def do_activate(self):
        self.window.set_application(self)
        self.window.present()

    def on_button_mainpage_clicked(self, widget):
        self.deck.set_visible_child(self.page_main)

    def on_button_show_log_clicked(self, widget):
        self.box_vte.set_visible(True)
        self.status_page.set_visible(False)
        self.btn_go_mainpage.set_visible(False)
        self.btn_show_log.set_visible(False)
        self.btn_close_logs.set_visible(True)

    def on_button_close_logs_clicked(self, widget):
        self.box_vte.set_visible(False)
        self.status_page.set_visible(True)
        self.btn_go_mainpage.set_visible(True)
        self.btn_show_log.set_visible(True)
        self.btn_close_logs.set_visible(False)

    def on_row_advanced_options_activated(self, widget):
        self.deck.set_visible_child(self.page_advanced)

    def on_button_about_clicked(self, widget):
        self.dialog_about.run()
        self.dialog_about.hide()

    """
        row functions is seperated to at least 2 subfunctions
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
        after the user selects one of them, the get_user, get_rootfs or get_mbr function will call the row function again (see self.pending_func)
    """
    def on_row_reinstall_grub_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            for child in self.carousel_questions.get_children():
               self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            if self.get_mbr(widget) == None:
                return
            if os.path.exists("/sys/firmware/efi/efivars") and self.get_clearEfivars(widget) == None: 
                return
            self.update_status_page(_("Reinstalling GRUB Bootloader"), "content-loading-symbolic", _("We're reinstalling the GRUB boot loader to ensure your system can start up properly. This process may take a few moments. Once complete, your computer should boot into Pardus as usual."), False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} mbr={} grub-reinstall".format(self.rootfs.name, self.mbr))
            else:
                self.vte_command("env subvolume={} disk={} mbr={} grub-reinstall".format(self.rootfs.root_subvol, self.rootfs.name, self.mbr))
            self.pending_func = None
        def post():
            self.update_status_page(_("GRUB Successfully Reinstalled"), "emblem-ok-symbolic", _("Great news! The GRUB boot loader has been successfully reinstalled on your system. You're all set to restart your computer and resume normal operation."), True, True)
            self.post_command = None
        pre()

    def on_row_fix_broken_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            for child in self.carousel_questions.get_children():
               self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            self.post_command = post
            self.update_status_page(_("Fixing Broken Packages"), "content-loading-symbolic", _("We're resolving issues with broken packages on your system to ensure everything works. This may take some time, but we're on it. Once complete, your system should be stable and ready for use."), False, False)
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} fix-broken-packages".format(self.rootfs.name))
            else:
                self.vte_command("env subvolume={} disk={} fix-broken-packages".format(self.rootfs.root_subvol, self.rootfs.name))
            self.pending_func = None
        def post():
            self.update_status_page(_("Packages Repaired"), "emblem-ok-symbolic", _("Great news! The broken packages on your system have been successfully repaired."), True, True)
            self.post_command = None
        pre()

    def on_row_reset_password_activated(self, widget):
        def pre():
            self.pending_func = pre
            for child in self.carousel_questions.get_children():
               self.carousel_questions.remove(child)
            self.deck.set_visible_child(self.page_loading)
            if self.get_rootfs(widget) == None:
                return None
            if self.get_user(widget) == None:
                return None
            self.password_page = self.new_page_input(_("Enter new password"), after_userdata)
            self.deck.set_visible_child(self.page_questions)
            self.pending_func = None
        def after_userdata(x):
            password1 = self.password_page.entry.get_text()
            password2 = self.password_page.entry_second.get_text()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Resetting password"), "content-loading-symbolic", _("We're resetting your password to provide access to your account. This process will only take a moment. Once complete, you'll be able to log in with your new password into your Pardus system."), False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} user={} pass1={} pass2={} reset-password".format(self.rootfs.name, self.user, password1, password2))
            else:
                self.vte_command("env subvolume={} user={} disk={} pass1={} pass2={} reset-password".format(self.rootfs.root_subvol, self.user, self.rootfs.name, password1, password2))
            self.user = None
        def post():
            self.update_status_page(_("Password Reset Completed"), "emblem-ok-symbolic", _("Your password has been successfully reset. You can now log in to your account with the new password."), True, True)
        
        if pre() == None:
            return

    def on_row_update_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            for child in self.carousel_questions.get_children():
               self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            self.update_status_page(_("Updating Software Packages"), "content-loading-symbolic", _("We're currently updating the software packages on your system to ensure you have the latest features and security enhancements. This process may take some time depending on the number of updates available. Please be patient."), False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} full-upgrade".format(self.rootfs.name))
            else:
                self.vte_command("env subvolume={} disk={} full-upgrade".format(self.rootfs.root_subvol, self.rootfs.name))
            self.pending_func = None
        def post():
            self.update_status_page(_("Software Packages Updated"), "emblem-ok-symbolic", _("Your system's software packages have been successfully updated. You now have the latest features and security patches installed."), True, True)
            self.post_command = None
        pre()

    def on_row_reinstall_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            for child in self.carousel_questions.get_children():
               self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            if self.get_mbr(widget) == None:
                return
            self.update_status_page(_("System Reinstallation"), "content-loading-symbolic", _("We're performing a clean reinstall of your system to ensure a fresh start. This process will reset your system to its original state, removing all applications."), False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} mbr={} pardus-reinstall".format(self.rootfs.name, self.mbr))
            else:
                self.vte_command("env subvolume={} disk={} mbr={} pardus-reinstall".format(self.rootfs.root_subvol, self.rootfs.name, self.mbr))
            self.pending_func = None
        def post():
            self.update_status_page(_("System Reinstallation Completed"), "emblem-ok-symbolic", _("Your system has been successfully reinstalled. Everything is now fresh and ready for you."), True, True)   
        pre()

    def on_row_repair_filesystem_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Detecting Partitions"), "content-loading-symbolic", _("We're scanning your system to locate available partitions."), False, False)
            partitions = self.list_partitions()
            if len(partitions) == 0:
                self.update_status_page(_("Unable to Detect Partitions"), "dialog-error-symbolic", _("We couldn't find any partitions on your system. This could indicate a problem with your disk or partition table. Please double-check your disk connections and configuration."), True, True)
                return

            partition_names = [part.name for part in partitions]
            partition_os = [part.operating_system for part in partitions]

            self.repair_page = self.new_page_listbox(_("Choose Partition for Filesystem Repair"), partition_names, partition_os, after_userdata)
            self.deck.set_visible_child(self.page_questions)
            self.pending_func = None
        def after_userdata(widget): 
            partition_for_repair = self.repair_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Repairing Filesystem on {}".format(partition_for_repair)), "content-loading-symbolic", _("We're currently repairing the filesystem on the selected partition. This process may take some time, depending on the size and severity of the issues found. Please be patient while we work to restore the partition's functionality."), False, False)
            self.post_command = post
            self.vte_command("env disk={} check-filesystem".format(partition_for_repair))
        def post():
            self.update_status_page(_("Filesystem Repair Successful"), "emblem-ok-symbolic", _("The filesystem has been successfully repaired. Your data should now be accessible without any issues."), True, True)
        pre()

    def on_row_reset_config_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Resetting User Settings"), "content-loading-symbolic", _("We're resetting your user configuration to its default state. This will revert any custom settings back to their original values. Please note that any personalized preferences will be lost. Once complete, your system will be refreshed and ready for use."), False, False)
            for child in self.carousel_questions.get_children():
               self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            if self.get_user(widget) == None:
                return
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env pardus-chroot /dev/{} su {} -c 'cd ; rm -rvf .dbus .cache .local .config'".format(self.rootfs.name, self.user))
            else:
                self.vte_command("env subvolume={} pardus-chroot /dev/{} su {} -c 'cd ; rm -rvf .dbus .cache .local .config'".format(self.rootfs.root_subvol, self.rootfs.name, self.user))
            self.pending_func = None
        def post():
            self.update_status_page(_("Configuration Reset Completed"), "emblem-ok-symbolic", _("Great news! Your user configuration has been successfully reset to its default settings."), True, True)
        pre()

    def on_row_dump_log_activated(self, widget):
        def pre():
            self.pending_func = pre
            for child in self.carousel_questions.get_children():
                self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            liveuser_home = self.run_command('grep "x:1000:" /etc/passwd | cut -f 6 -d ":"')
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Extracting System Logs"), "content-loading-symbolic", _("We're collecting important system logs and placing them in the '{}' directory as you requested. These logs contain helpful information about your system's activity and any issues it may be experiencing. Depending on how much information there is, this might take a little time. Thanks for waiting while we gather this data.".format(liveuser_home)), False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} dump-info-log {}".format(self.rootfs.name, liveuser_home))
            else:
                self.vte_command("env subvolume={} disk={} dump-info-log {}".format(self.rootfs.root_subvol, self.rootfs.name, liveuser_home))
            self.pending_func = None
        def post():
            self.update_status_page(_("System Logs Extracted"), "emblem-ok-symbolic", _("Great news! The system logs have been successfully extracted. This valuable information can help diagnose any issues with your system."), True, True)
        pre()

    def on_row_chroot_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Entering Chroot Environment"), "content-loading-symbolic", _("We're accessing a special system environment called chroot at your request. This allows you to make changes as if you were working directly on your installed operating system. Please wait while we set up this environment to address your needs."), False, True)
            for child in self.carousel_questions.get_children():
                self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            if self.get_user(widget) == None:
                return
            self.btn_show_log.clicked()
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} pardus-chroot /dev/{} su {} -".format(self.rootfs.name, self.rootfs.name, self.user))
            else:
                self.vte_command("env subvolume={} pardus-chroot /dev/{} su {} -".format(self.rootfs.root_subvol ,self.rootfs.name, self.user))
            self.user = None
            self.pending_func = None
        def post():
            self.btn_close_logs.clicked()
            self.update_status_page(_("Chroot Process Successfully Concluded"), "emblem-ok-symbolic", _("The chroot process has finished successfully"), True, True)
        pre()

    def update_status_page(self, title, icon_name, description, stop_spinner=False, enable_mainpage=True):
        self.status_page.set_title(title)
        self.status_page.set_icon_name(icon_name)
        self.status_page.set_description(description)
        self.btn_go_mainpage.set_sensitive(enable_mainpage)
        self.spinner_loading.start()
        if stop_spinner:
            self.spinner_loading.stop()

    def vte_command(self, command):
        try:
            env_vars = [f'{key}={value}' for key, value in os.environ.items()]
            self.vte_terminal.reset(True, True)
            exec = self.vte_terminal.spawn_async(
                Vte.PtyFlags.DEFAULT, os.environ['HOME'], ["/bin/bash", "-c", command], env_vars, GLib.SpawnFlags.SEARCH_PATH, None, None, -1, None)
        except Exception as e:
            # write error to stderr
            sys.stderr.write(str(e) + "\n")
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", str(e), True, True)

    def vte_cb(self, pid, error):
        if error != None or pid == -1:
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", _("An error occurred before the command has been executed"), True, True)
            return
    def vte_exited(self, widget, status):
        exit_status = os.waitstatus_to_exitcode(status)
        if exit_status != 0:
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", _("An error occured while executing the command. Please check the logs"), True, True)
            return
        if self.post_command == None:
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", _("An error occurred after the command has been executed."), True, True)
            return
        Thread(target=self.post_command).start()
        
    def run_command(self, command: str):
        try:
            output = subprocess.check_output(["/bin/bash", "-c", command]).decode("utf-8").strip()
            return output
        except Exception as e:
            sys.stderr.write(str(e) + "\n")            
            self.update_status_page(_("An error occured"), "dialog-error-symbolic", str(e), True, True)
            return None

    def get_rootfs(self,widget):
        def pre():
            if not hasattr(self, 'rootfs') or self.rootfs == None:
                self.rootfs_list = self.detect_rootfs()
                if len(self.rootfs_list) == 0:
                    self.update_status_page(_("Root Filesystem Missing"), "dialog-error-symbolic", _("We couldn't locate the root filesystem on your system. This could be due to a disk failure, misconfiguration, or other issues. Please ensure that your disk is properly connected and configured."), True, True)
                    return None
                elif len(self.rootfs_list) > 1:
                    partition_names = [part.name for part in self.rootfs_list]
                    partition_os = [part.operating_system for part in self.rootfs_list]
                    self.rootfs_page = self.new_page_listbox(_("Select a root filesystem"), partition_names, partition_os, post)
                    self.deck.set_visible_child(self.page_questions)
                    return None
                self.rootfs = self.rootfs_list[0]
            return self.rootfs
        def post(widget):
            selected = self.rootfs_page.listbox.get_selected_row().get_title()
            self.rootfs = next((x for x in self.rootfs_list if x.name == selected), None)
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Root Filesystem Chosen"), "emblem-ok-symbolic", _("You've selected the root filesystem for further action."), False, False)
            if self.pending_func != None:
                Thread(target=self.pending_func).start()

        return pre()

    def get_user(self, widget):
        def pre():
            if not hasattr(self, 'user') or self.user == None :
                users = self.list_users(self.rootfs)
                if len(users) == 0:
                    self.update_status_page(_("No Users Detected"), "dialog-error-symbolic", _("We couldn't find any users on your system. This could indicate an issue with user accounts or system configuration. Please ensure that users are properly configured."), True, True)
                    return None
                elif len(users) > 1:
                    self.users_page = self.new_page_listbox(_("Select a user"), users, None, after_userdata)
                    self.deck.set_visible_child(self.page_questions)
                    return None
                self.user = users[0]
            return self.user
        def after_userdata(widget):
            self.user = self.users_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("User Chosen"), "emblem-ok-symbolic", _( "You've selected a user for further action. This step is important for making changes specific to the chosen user."), False, False)
            if self.pending_func != None:
                Thread(target=self.pending_func).start()
        return pre()

    def get_mbr(self,widget):
        def pre():
            if not hasattr(self, 'mbr') or self.mbr == None:
                mbrs = self.list_mbrs()
                if len(mbrs) == 0:
                    self.update_status_page(_("Master Boot Record (MBR) Missing"), "dialog-error-symbolic", _("We couldn't locate the Master Boot Record (MBR) on your system. This critical component is necessary for booting your system. Please check your disk connections and configuration."), True, True)
                    return None
                elif len(mbrs) > 1:
                    self.mbr_page = self.new_page_listbox(_("Select the Master Boot Record (MBR)"), mbrs, None, after_userdata)
                    self.deck.set_visible_child(self.page_questions)
                    return None
                self.mbr = mbrs[0]
            return self.mbr
        def after_userdata(widget):
            self.mbr = self.mbr_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("MBR chosen"), "emblem-ok-symbolic", _("You've successfully selected the Master Boot Record (MBR). This selection is essential for configuring your system's boot process."), False, False)
            if self.pending_func != None:
                Thread(target=self.pending_func).start()
        return pre()

    def get_clearEfivars(self,widget):
        def pre():
            if not hasattr(self, 'clear_efivars') or self.clear_efivars == None:
                self.clear_efipage = self.new_page_listbox(_("Are you sure you want to clear efivars?"), [_("Yes"), _("No")], None, after_userdata)
                self.deck.set_visible_child(self.page_questions)
                return None
            return self.clear_efivars
        def after_userdata(widget):
            if self.clear_efipage.listbox.get_selected_row().get_title() == _("Yes"):
                self.clear_efivars = 'y'
            else:
                self.clear_efivars = 'n'
            self.deck.set_visible_child(self.page_loading)
            if self.pending_func != None:
                Thread(target=self.pending_func).start()
        return pre()

    def get_operating_system(self,partitions):
        for part in partitions:
            part.operating_system = self.run_command('env parts={} search-operating-system'.format(part.name)).split(":")[0].replace('"', '').strip()
        return partitions

    def detect_rootfs(self):
        pardus_rootfs = []
        rootfs = []
        partitions = self.list_partitions()
        self.update_status_page(_("Searching for Root Filesystem"), "content-loading-symbolic", _("We're searching for the root filesystem on your system. This is essential for proper system operation. Please wait while we locate the root filesystem. Thank you for your patience."), False, False)
        for part in partitions:
            if part.mountpoint == "/":
                continue
            TEMPDIR = self.run_command('mktemp -d')
            if part.mountpoint != "":
                self.run_command("umount -lf {}".format(part.mountpoint))

            self.run_command('mount {} {}'.format(part.path,TEMPDIR))
            if os.path.exists(TEMPDIR + "/etc/os-release"):
                part.is_rootfs = True
                rootfs.append(part)
                with open(TEMPDIR + "/etc/os-release") as f:
                    for line in f:
                        if "pardus" in line:
                            part.is_pardus_rootfs = True
                            pardus_rootfs.append(part)
                            break
            if part.fstype == "btrfs" and not os.path.exists(TEMPDIR + "/etc/os-release"):
                subvol, part.is_rootfs, part.is_pardus_rootfs = self.detect_btrfs_rootfs_subvolume(TEMPDIR)
                if subvol != None:
                    part.root_subvol = subvol
                if part.is_pardus_rootfs:
                    pardus_rootfs.append(part)
                if part.is_rootfs:
                    rootfs.append(part)

            self.run_command('umount -l ' + TEMPDIR)
            self.run_command('rmdir ' + TEMPDIR)
        if len(pardus_rootfs) > 0:
            return pardus_rootfs
        return rootfs

    def detect_btrfs_rootfs_subvolume(self, mountdir):
        self.update_status_page(_("Searching for Btrfs Root Filesystem Subvolume"), "content-loading-symbolic", _("We're searching for the Btrfs root filesystem subvolume on your system. This is essential for proper system operation. Please wait while we locate the Btrfs root filesystem subvolume. Thank you for your patience."), False, False)
        output = self.run_command("btrfs subvolume list " + mountdir + " | awk '{print $9}'")
        for subvol in output.split("\n"):
            if os.path.exists("{}/{}/etc/os-release".format(mountdir, subvol)):
                is_rootfs = True
                is_pardus_rootfs = False
                with open("{}/{}/etc/os-release".format(mountdir, subvol)) as f:
                    for line in f:
                        if "pardus" in line:
                            is_pardus_rootfs = True
                            break
                return subvol, is_rootfs, is_pardus_rootfs
        return None, False, False

    def list_partitions(self):
        parts = self.run_command('ls /sys/block/* | grep "[0-9]$" | grep -Ev "loop|sr"')
        partitions = []
        for part in parts.split():
            partition = Partition()
            partition.name = part
            partition.path = "/dev/" + part
            for x in ["FSTYPE", "UUID", "SIZE", "LABEL", "MOUNTPOINT"]:
                output = self.run_command('lsblk -no {} {}'.format(x,partition.path))
                partition.__setattr__(x.lower(), output.strip())
            partitions.append(partition)
        partitions = self.get_operating_system(partitions)
        return partitions

    def list_users(self, rootfs):
        TEMPDIR = self.run_command('mktemp -d')
        if self.rootfs.root_subvol != None:
            self.run_command("mount -o subvol={} /dev/{} {}".format(rootfs.root_subvol, rootfs.name, TEMPDIR))
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

    def new_page_listbox(self, label_text, row_titles, row_subtitles, btn_next_clicked_signal):
        page = Questions_page_listbox(label_text)
        def on_questions_row_activated(widget):
            page.button.set_sensitive(True)

        if row_subtitles == None or len(row_subtitles) == 0:
            row_subtitles = ["" for x in row_titles]
        elif len(row_titles) != len(row_subtitles):
            raise ValueError("row_titles and row_subtitles must have the same length")

        page.button.connect('clicked', btn_next_clicked_signal)
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
        return page

    def new_page_input(self, label_text, btn_continue_clicked_signal):
        page = Questions_page_password_input(label_text)
        def input_change_event(widget):
            entry_text = page.entry.get_text()
            entry_second_text = page.entry_second.get_text()
            if entry_text != entry_second_text and (entry_text != "" and entry_second_text != ""):
                page.warn_entry.set_visible(True)
                page.button.set_sensitive(False)
            if entry_text == entry_second_text and entry_text != "":
                page.warn_entry.set_visible(False)
                page.button.set_sensitive(True)

        page.entry.connect("changed", input_change_event)
        page.entry_second.connect("changed", input_change_event)
        page.button.connect('clicked', btn_continue_clicked_signal)
        self.carousel_questions.insert(page, -1)
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
    def __init__(self, label_text):
        super().__init__()
        self.label = Gtk.Label()
        self.label.set_text(label_text)
        self.label.set_visible(True)
        self.add(self.label)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.get_style_context().add_class('content')
        self.listbox.set_visible(True)
        self.listbox.set_vexpand(True)
        self.listbox.set_hexpand(True)
        self.add(self.listbox)

        self.button = Gtk.Button()
        self.button.set_label(_("Continue"))
        self.button.set_visible(True)
        self.button.set_sensitive(False)
        self.button.set_hexpand(True)
        self.button.set_vexpand(False)
        self.button.set_halign(Gtk.Align.FILL)
        self.button.set_valign(Gtk.Align.END)
        self.button.set_image(Gtk.Image.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON))
        self.button.set_always_show_image(True)
        self.button.set_image_position(Gtk.PositionType.RIGHT)
        self.add(self.button)

class Questions_page_password_input(Page):
    def __init__(self, label_text):
        super().__init__()
        self.label = Gtk.Label()
        self.label.set_text(label_text)
        self.label.set_visible(True)
        self.add(self.label)

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

        self.button = Gtk.Button()
        self.button.set_label(_("Continue"))
        self.button.set_visible(True)
        self.button.set_sensitive(False)
        self.button.set_hexpand(True)
        self.button.set_vexpand(True)
        self.button.set_halign(Gtk.Align.FILL)
        self.button.set_valign(Gtk.Align.END)
        self.button.set_image(Gtk.Image.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON))
        self.button.set_always_show_image(True)
        self.button.set_image_position(Gtk.PositionType.RIGHT)
        self.add(self.button)

class Partition(object):
    def __init__(self):
        self.name = None
        self.path = None
        self.fstype = None
        self.uuid = None
        self.size = 0
        self.label = None
        self.is_rootfs = False
        self.is_pardus_rootfs = False
        self.root_subvol = None
        self.mountpoint = None
        self.operating_system = None

app = Application()    
app.run(sys.argv)