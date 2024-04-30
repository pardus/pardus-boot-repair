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

    def do_activate(self):
        self.window.set_application(self)
        self.window.present()

    def on_button_mainpage_clicked(self, widget):
        self.deck.set_visible_child(self.page_main)

    def on_row_advanced_options_activated(self, widget):
        self.deck.set_visible_child(self.page_advanced)

if __name__ == "__main__":
    app = Application()
    app.run(sys.argv)