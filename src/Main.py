import sys
import os
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")
from gi.repository import Gtk, Handy, GLib, Gio

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

    def do_activate(self):
        self.window.set_application(self)
        self.window.present()

    def on_button_mainpage_clicked(self, widget):
        self.deck.set_visible_child(self.page_main)

    def on_row_advanced_options_activated(self, widget):
        self.deck.set_visible_child(self.page_advanced)

    def on_questions_row_activated(self, widget):
        self.button_next.set_sensitive(True)

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