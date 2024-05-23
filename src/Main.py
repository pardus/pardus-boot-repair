#!/usr/bin/env python3
import sys
import os
import gi
import subprocess
from gettext import gettext as _
gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")
gi.require_version("Vte", "2.91")
from threading import Thread
from gi.repository import Gtk, Handy, Gdk, Gio, GLib, Vte

Handy.init()

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
        self.button_next = self.builder.get_object("button_next")

        # loading page
        self.btn_go_mainpage = self.builder.get_object("button_loading_to_mainpage")
        self.btn_close_logs = self.builder.get_object("button_close_logs")
        self.status_page = self.builder.get_object("page_status")
        self.spinner_loading = self.builder.get_object("spinner_page_loading")
        self.btn_show_log = self.builder.get_object("button_show_log")
        self.box_vte = self.builder.get_object("box_vte")
        self.vte_terminal = Vte.Terminal()
        self.box_vte.add(self.vte_terminal)
        self.vte_terminal.show()

    def do_activate(self):
        self.window.set_application(self)
        self.window.present()

    def on_button_mainpage_clicked(self, widget):
        self.deck.set_visible_child(self.page_main)

    def on_button_show_log_clicked(self, widget):
        self.box_vte.set_visible(True)
        self.status_page.set_visible(False)
        self.btn_go_mainpage.set_visible(False)
        self.btn_close_logs.set_visible(True)

    def on_button_close_logs_clicked(self, widget):
        self.box_vte.set_visible(False)
        self.status_page.set_visible(True)
        self.btn_go_mainpage.set_visible(True)
        self.btn_close_logs.set_visible(False)

    def on_row_advanced_options_activated(self, widget):
        self.deck.set_visible_child(self.page_advanced)

    def on_questions_row_activated(self, widget):
        self.button_next.set_sensitive(True)

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
            self.update_status_page(_("Reinstalling grub..."), "dialog-information", "", False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} mbr={} pardus-reinstall".format(self.rootfs.name, self.mbr))
            else:
                self.vte_command("env subvolume={} disk={} mbr={} grub-reinstall".format(self.rootfs.root_subvol, self.rootfs.name, self.mbr))
        def post(Terminal, widget):
            self.update_status_page(_("Grub reinstalled"), "dialog-information", "", True, True)
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
            self.update_status_page(_("Trying to fix broken packages..."), "dialog-information", "", False, False)
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} fix-broken-packages".format(self.rootfs.name))
            else:
                self.vte_command("env subvolume={} disk={} fix-broken-packages".format(self.rootfs.root_subvol, self.rootfs.name))
        def post(Terminal, widget):
            self.update_status_page(_("Packages fixed"), "dialog-information", "", True, True)
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
            self.password_page = self.new_page_input(_("Enter new password"))
            self.deck.set_visible_child(self.page_questions)
            self.button_next.connect("clicked", after_userdata)
        def after_userdata(x):
            password1 = self.password_page.entry.get_text()
            password2 = self.password_page.entry_second.get_text()
            if password1 != password2:
                self.password_page.warn_entry.set_visible(True)
                return
            self.password_page.warn_entry.set_visible(False)
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Resetting password..."), "content-loading", "", False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} user={} pass1={} pass2={} reset-password".format(self.rootfs.name, self.user, password1, password2))
            else:
                self.vte_command("env subvolume={} user={} disk={} pass1={} pass2={} reset-password".format(self.rootfs.root_subvol, self.user, self.rootfs.name, password1, password2))
        def post(x, widget):
            self.user = None
            self.update_status_page(_("Password reset"), "dialog-information", "", True, True)
        
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
            self.update_status_page(_("Updating packages..."), "dialog-information", "", False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} full-upgrade".format(self.rootfs.name))
            else:
                self.vte_command("env subvolume={} disk={} full-upgrade".format(self.rootfs.root_subvol, self.rootfs.name))
        def post(Terminal, widget):
            self.update_status_page(_("Packages updated"), "dialog-information", "", True, True)
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
            self.update_status_page(_("Reinstalling packages..."), "dialog-information", "", False, False)
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} mbr={} pardus-reinstall".format(self.rootfs.name, self.mbr))
            else:
                self.vte_command("env subvolume={} disk={} mbr={} pardus-reinstall".format(self.rootfs.root_subvol, self.rootfs.name, self.mbr))
        def post(Terminal, widget):
            self.update_status_page(_("Reinstalled successfully"), "dialog-information", "", True, True)   
        pre()

    def on_row_repair_filesystem_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Searching for partitions..."), "content-loading", "", False, False)
            partitions = self.list_partitions()
            if len(partitions) == 0:
                self.update_status_page(_("No partitions found"), "dialog-error", _("No partitions found"), True, True)
                return

            partition_names = [part.name for part in partitions]
            self.repair_page = self.new_page_listbox(_("Select a partition to repair"), partition_names)
            self.deck.set_visible_child(self.page_questions)
            self.button_next.connect("clicked", after_userdata)
        def after_userdata(widget): 
            partition_for_repair = self.repair_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Repairing partition..."), "content-loading", "", False, False)
            self.post_command = post
            self.vte_command("env disk={} check-filesystem".format(partition_for_repair))
        def post(x, widget):
            self.update_status_page(_("Partition repaired"), "dialog-information", "", True, True)
        pre()

    def on_row_reset_config_activated(self, widget):
        def pre():
            self.pending_func = pre
            self.deck.set_visible_child(self.page_loading)
            for child in self.carousel_questions.get_children():
               self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            users = self.list_users(self.rootfs)
            if len(users) == 0:
                self.update_status_page(_("No users found"), "dialog-error", _("No users found"), True, True)
                return
            self.update_status_page(_("Resetting configuration..."), "content-loading", "", False, False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env pardus-chroot /dev/{} su {} -c 'cd ; rm -rvf .dbus .cache .local .config'".format(self.rootfs.name ,users[0]))
            else:
                self.vte_command("env subvolume={} pardus-chroot /dev/{} su {} -c 'cd ; rm -rvf .dbus .cache .local .config'".format(self.rootfs.root_subvol, self.rootfs.name ,users[0]))
        def post(Terminal, widget):
            self.update_status_page(_("Configuration reset"), "dialog-information", "", True, True)
        pre()

    def on_row_dump_log_activated(self, widget):
        def pre():
            self.pending_func = pre
            for child in self.carousel_questions.get_children():
                self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Dumping logs..."), "dialog-information", "", False, False)
            liveuser_home = self.run_command('grep "x:1000:" /etc/passwd | cut -f 6 -d ":"')
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} dump-info-log {}".format(self.rootfs.name, liveuser_home))
            else:
                self.vte_command("env subvolumes={} disk={} dump-info-log {}".format(self.rootfs.root_subvol, self.rootfs.name, liveuser_home))
        def post(Terminal, widget):
            self.update_status_page(_("Logs dumped"), "dialog-information", "", True, True)
        pre()

    def on_row_chroot_activated(self, widget):
        def pre():
            self.pending_func = pre
            for child in self.carousel_questions.get_children():
                self.carousel_questions.remove(child)
            if self.get_rootfs(widget) == None:
                return
            if self.get_user(widget) == None:
                return
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Chrooting..."), "dialog-information", "", False, True)
            self.btn_close_logs.set_visible(True)
            self.btn_go_mainpage.set_visible(False)
            self.box_vte.set_visible(True)
            self.status_page.set_visible(False)
            self.post_command = post
            if self.rootfs.root_subvol == None:
                self.vte_command("env disk={} pardus-chroot /dev/{} su {} -".format(self.rootfs.name, self.rootfs.name, self.user))
            else:
                self.vte_command("env subvolume={} pardus-chroot /dev/{} su {} -".format(self.rootfs.root_subvol ,self.rootfs.name, self.user))
        def post(Terminal, widget):
            self.btn_close_logs.set_visible(False)
            self.btn_go_mainpage.set_visible(True)
            self.box_vte.set_visible(False)
            self.status_page.set_visible(True)
            self.update_status_page(_("Chrooted"), "dialog-information", "", True, True)
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
            exec = self.vte_terminal.spawn_async(
                Vte.PtyFlags.DEFAULT, os.environ['HOME'], ["/bin/bash", "-c", command], [], GLib.SpawnFlags.SEARCH_PATH, None, None, -1, None, self.vte_cb)
        except Exception as e:
            # write error to stderr
            sys.stderr.write(str(e) + "\n")            
            self.update_status_page(_("An error occured"), "dialog-error", str(e), True, True)

    def vte_cb(self, widget, status, user_data):
        if self.post_command != None:
            self.vte_terminal.connect("child-exited", self.post_command)

    def run_command(self, command: str):
        try:
            output = subprocess.check_output(["/bin/bash", "-c", command]).decode("utf-8").strip()
            return output
        except Exception as e:
            sys.stderr.write(str(e) + "\n")            
            self.update_status_page(_("An error occured"), "dialog-error", str(e), True, True)
            return None

    def get_rootfs(self,widget):
        def pre():
            if not hasattr(self, 'rootfs') or self.rootfs == None:
                rootfs_list = self.detect_rootfs()
                if len(rootfs_list) == 0:
                    self.update_status_page(_("No rootfs found"), "dialog-error", _("No rootfs found"), True, True)
                    return None
                elif len(rootfs_list) > 1:
                    rootfs_names = []
                    for part in rootfs_list:
                        rootfs_names.append(part.name)
                    self.rootfs_page = self.new_page_listbox(_("Select a rootfs"), rootfs_names)
                    self.deck.set_visible_child(self.page_questions)
                    self.button_next.connect("clicked", post)
                    return None
                self.rootfs = rootfs_list[0]
            return self.rootfs
        def post():
            selected = self.rootfs_page.listbox.get_selected_row().get_title()
            self.rootfs = next((x for x in rootfs_list if x.name == selected), None)
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Rootfs selected"), "dialog-information", "", False, False)
            self.button_next.disconnect_by_func(post)
            if self.pending_func != None:
                Thread(target=self.pending_func).start()
                self.pending_func = None

        return pre()

    def get_user(self, widget):
        def pre():
            if not hasattr(self, 'user') or self.user == None:
                users = self.list_users(self.rootfs)
                if len(users) == 0:
                    self.update_status_page(_("No users found"), "dialog-error", _("No users found"), True, True)
                    return None
                elif len(users) > 1:
                    self.users_page = self.new_page_listbox(_("Select a user"), users)
                    self.deck.set_visible_child(self.page_questions)
                    self.button_next.connect("clicked", after_userdata)
                    return None
                self.user = users[0]
            return self.user
        def after_userdata(widget):
            self.user = self.users_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("User selected"), "dialog-information", "", False, False)
            self.button_next.disconnect_by_func(after_userdata)
            if self.pending_func != None:
                Thread(target=self.pending_func).start()
                self.pending_func = None
        return pre()

    def get_mbr(self,widget):
        def pre():
            if not hasattr(self, 'mbr') or self.mbr == None:
                mbrs = self.list_mbrs()
                if len(mbrs) == 0:
                    self.update_status_page(_("No MBR found"), "dialog-error", _("No MBR found"), True, True)
                    return None
                elif len(mbrs) > 1:
                    self.mbr_page = self.new_page_listbox(_("Select a MBR"), mbrs)
                    self.deck.set_visible_child(self.page_questions)
                    self.button_next.connect("clicked", after_userdata)
                    return None
                self.mbr = mbrs[0]
            return self.mbr
        def after_userdata(widget):
            self.mbr = self.mbr_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("MBR selected"), "dialog-information", "", False, False)
            self.button_next.disconnect_by_func(after_userdata)            
            if self.pending_func != None:
                Thread(target=self.pending_func).start()
                self.pending_func = None
        return pre()

    def get_clearEfivars(self,widget):
        def pre():
            if not hasattr(self, 'clear_efivars') or self.clear_efivars == None:
                self.clear_efipage = self.new_page_listbox(_("Are you sure you want to clear efivars?"), [_("Yes"), _("No")])
                self.deck.set_visible_child(self.page_questions)
                self.button_next.connect("clicked", after_userdata)
                return None
            return self.clear_efivars
        def after_userdata(widget):
            if self.clear_efipage.listbox.get_selected_row().get_title() == _("Yes"):
                self.clear_efivars = 'y'
            else:
                self.clear_efivars = 'n'
            self.deck.set_visible_child(self.page_loading)
            self.button_next.disconnect_by_func(after_userdata)
            if self.pending_func != None:
                Thread(target=self.pending_func).start()
                self.pending_func = None
        return pre()
    def detect_rootfs(self):
        pardus_rootfs = []
        rootfs = []
        partitions = self.list_partitions()
        self.update_status_page(_("Searching for rootfs..."), "content-loading", "", False, False)
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
                self.run_command('rm -rf ' + TEMPDIR)

            self.run_command('umount -l ' + TEMPDIR)
            self.run_command('rm -rf ' + TEMPDIR)
        if len(pardus_rootfs) > 0:
            return pardus_rootfs
        return rootfs

    def detect_btrfs_rootfs_subvolume(self, mountdir):
        self.update_status_page(_("Searching for btrfs rootfs subvolume..."), "content-loading", "", False, False)
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
        mbrs = self.run_command(
            'ls /sys/block/ | grep -Ev "loop|sr"')
        return mbrs.split()

    def new_page_listbox(self, label_text, Row_titles):
        page = Questions_page_listbox(label_text)
        for title in Row_titles:
            row = Handy.ActionRow()
            row.set_title(title)
            row.set_visible(True)
            row.get_style_context().add_class('activatable')
            row.set_property('activatable', True)
            row.connect("activate", self.on_questions_row_activated)
            page.listbox.insert(row, -1)
        self.carousel_questions.insert(page, -1)
        return page

    def new_page_input(self, label_text):
        page = Questions_page_password_input(label_text)
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
        self.add(self.listbox)

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

app = Application()    
app.run(sys.argv)