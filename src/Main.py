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

    def on_row_advanced_options_activated(self, widget):
        self.deck.set_visible_child(self.page_advanced)

    def on_questions_row_activated(self, widget):
        self.button_next.set_sensitive(True)

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
                callerfunc = lambda n=0: sys._getframe(n + 1).f_code.co_name
                if len(rootfs_list) == 0:
                    self.update_status_page(_("No rootfs found"), "dialog-error", _("No rootfs found"), True, True)
                    return None
                elif len(rootfs_list) > 1:
                    rootfs_names = []
                    for part in rootfs_list:
                        rootfs_names.append(part.name)
                    self.rootfs_page = self.new_page_listbox(_("Select a rootfs"), rootfs_names)
                    self.deck.set_visible_child(self.page_questions)
                    self.pending_widget = widget
                    print(callerfunc(1))
                    self.pending_func = getattr(self,callerfunc(1))
                    self.button_next.connect("clicked", post)
                    self.pending_widget = widget
                    return None
                self.rootfs = rootfs_list[0].name
            return self.rootfs
        def post():
            self.rootfs = self.rootfs_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("Rootfs selected"), "dialog-information", "", False, False)
            self.button_next.disconnect_by_func(post)
            Thread(target=self.pending_func, args=(self.pending_widget,)).start()
            self.pending_func = None
            self.pending_widget = None

        return pre()

    def get_user(self, widget):
        def pre():
            callerfunc = lambda n=0: sys._getframe(n + 1).f_code.co_name
            if not hasattr(self, 'user') or self.user == None:
                users = self.list_users(self.rootfs)
                if len(users) == 0:
                    self.update_status_page(_("No users found"), "dialog-error", _("No users found"), True, True)
                    return None
                elif len(users) > 1:
                    self.users_page = self.new_page_listbox(_("Select a user"), users)
                    self.pending_func = getattr(self,callerfunc(2))
                    self.pending_widget = widget
                    self.deck.set_visible_child(self.page_questions)
                    self.button_next.connect("clicked", after_userdata)
                    return None
                self.user = users[0]
            return self.user
        def after_userdata(widget):
            self.user = self.users_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("User selected"), "dialog-information", "", False, False)
            Thread(target=self.pending_func, args=(self.pending_widget,)).start()
            self.pending_func = None
            self.pending_widget = None
            self.button_next.disconnect_by_func(after_userdata)
        return pre()

    def get_mbr(self,widget):
        def pre():
            callerfunc = lambda n=0: sys._getframe(n + 1).f_code.co_name
            if not hasattr(self, 'mbr') or self.mbr == None:
                mbrs = self.list_mbrs()
                if len(mbrs) == 0:
                    self.update_status_page(_("No MBR found"), "dialog-error", _("No MBR found"), True, True)
                    return None
                elif len(mbrs) > 1:
                    self.mbr_page = self.new_page_listbox(_("Select a MBR"), mbrs)
                    self.deck.set_visible_child(self.page_questions)
                    self.pending_func = getattr(self,callerfunc(1))
                    self.button_next.connect("clicked", after_userdata)
                    return None
                self.mbr = mbrs[0]
            return self.mbr
        def after_userdata(widget):
            self.mbr = self.mbr_page.listbox.get_selected_row().get_title()
            self.deck.set_visible_child(self.page_loading)
            self.update_status_page(_("MBR selected"), "dialog-information", "", False, False)
            self.button_next.disconnect_by_func(after_userdata)            
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

    def list_users(self, rootfs_name):
        self.run_command("mount /dev/{} /mnt".format(rootfs_name))
        output = self.run_command(
            'grep -e ":x:[0-9][0-9][0-9][0-9]:" /mnt/etc/passwd | cut -f 1 -d ":"')
        if output == "":
            return []
        self.run_command("umount -lf /mnt")
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

if __name__ == "__main__":
    app = Application()
    app.run(sys.argv)