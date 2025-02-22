# Copyright 2004-2022 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# A map from an image tag to the properties used by speech bubbles with
# that image tag.
default bubble.tag_properties = { }

# A list of (image_tag, tlid) pairs represening the dialogue that is
# on the screen now.
default bubble.current_dialogue = [ ]

init -1050 python in bubble:

    from store import config, ADVCharacter, Character, JSONDB, Action, Frame

    # This gets set to true if at least one character that uses a speech bubble has been defined.
    active = False

    # The path to the json file the bubble database is stored in.
    db_filename = "bubble.json"

    # The number of rows and columns in the bubble database.
    cols = 24
    rows = 24

    # The default window area rectangle. This is expressed as squares, where units
    # are defined by the rows and columns.
    default_area = (0, 18, 24, 6)

    # The property that the area is supplied as.
    area_property = "window_area"

    # Additional properties that the player can use to customize the bubble.
    # This is a map from a property name to a list of choices that are cycled
    # through.
    properties = {
        "default" : { }
    }

    # The property group names, in order.
    properties_order = [ "default" ]

    # This is set to the JSONDB object that stores the bubble database,
    # or None if the databse doesn't exist yet.
    db = None


    def scene_callback(layer):
        global tag_properties

        if layer == "master":
            tag_properties = { }


    def character_callback(event, interact=True, **kwargs):
        global current_dialogue

        if event == "end" and interact:
            current_dialogue = [ ]


    class BubbleCharacter(ADVCharacter):

        def __init__(self, *args, **kwargs):

            open_db = kwargs.pop("_open_db", True)

            kwargs.setdefault("statement_name", "say-bubble")

            super(BubbleCharacter, self).__init__(*args, **kwargs)

            if not open_db:
                return

            if self.image_tag is None:
                raise Exception("BubbleCharacter require an image tag (the image='...' parameter).")

            global active
            global db

            active = True

            if db is None and open_db:
                db = JSONDB(db_filename)

            if character_callback not in config.all_character_callbacks:
                config.all_character_callbacks.insert(0, character_callback)

            if scene_callback not in config.scene_callbacks:
                config.scene_callbacks.insert(0, scene_callback)

        def bubble_default_properties(self, image_tag):
            """
            This is responsible for creating a reasonable set of bubble properties
            for the given image tag.
            """

            rv = { }

            xgrid = config.screen_width / cols
            ygrid = config.screen_height / rows

            default_area_rect = [
                int(default_area[0] * xgrid),
                int(default_area[1] * ygrid),
                int(default_area[2] * xgrid),
                int(default_area[3] * ygrid)
            ]

            return {
                "area" : default_area_rect,
                "properties" : properties_order[0]
            }

        def do_show(self, who, what, multiple=None, extra_properties=None):

            if extra_properties is None:
                extra_properties = { }
            else:
                extra_properties = dict(extra_properties)

            image_tag = self.image_tag

            if image_tag not in tag_properties:
                tag_properties[image_tag] = self.bubble_default_properties(image_tag)

            tlid = renpy.get_translation_identifier()

            if tlid is not None:
                for k, v in db[tlid].items():
                    tag_properties[image_tag][k] = v

                current_dialogue.append((image_tag, tlid))

            properties_key = tag_properties[image_tag]["properties"]

            extra_properties.update(properties.get(properties_key, { }))
            extra_properties[area_property] = tag_properties[image_tag]["area"]

            return super(BubbleCharacter, self).do_show(who, what, multiple=multiple, extra_properties=extra_properties)

    class CycleBubbleProperty(Action):
        """
        This is an action that causes the property groups to be cycled
        through.
        """

        def __init__(self, image_tag, tlid):
            self.image_tag = image_tag
            self.tlid = tlid

        def get_selected(self):
            return "properties" in db[self.tlid]

        def __call__(self):

            current = tag_properties[self.image_tag]["properties"]

            try:
                idx = properties_order.index(current)
            except ValueError:
                idx = 0

            idx = (idx + 1) % len(properties_order)

            db[self.tlid]["properties"] = properties_order[idx]
            renpy.rollback(checkpoints=0, force=True, greedy=True)

        def alternate(self):
            if "properties" in db[self.tlid]:
                del db[self.tlid]["properties"]
                renpy.rollback(checkpoints=0, force=True, greedy=True)

    class SetWindowArea(Action):
        """
        An action that displays the area picker to select the window area.
        """

        def __init__(self, image_tag, tlid):
            self.image_tag = image_tag
            self.tlid = tlid

        def __call__(self):
            renpy.show_screen("_bubble_window_area_editor", self)
            renpy.restart_interaction()

        def get_selected(self):
            return "area" in db[self.tlid]

        def finished(self, rect):
            rect = list(rect)
            db[self.tlid]["area"] = rect
            renpy.rollback(checkpoints=0, force=True, greedy=True)

        def alternate(self):
            if "area" in db[self.tlid]:
                del db[self.tlid]["area"]
                renpy.rollback(checkpoints=0, force=True, greedy=True)

    def GetCurrentDialogue():
        """
        Returns the properties of the current bubble.

        Returns a list of (tlid, property list) pairs, where each property list
        contains a (name, action) pair.
        """

        rv = [ ]

        for image_tag, tlid in current_dialogue:
            property_list = [ ]

            property_list.append((
                "area={!r}".format(tag_properties[image_tag]["area"]),
                SetWindowArea(image_tag, tlid)))

            property_list.append((
                "properties={}".format(tag_properties[image_tag]["properties"]),
                CycleBubbleProperty(image_tag, tlid)))

            rv.append((image_tag, property_list))

        return rv

    # A character that inherits from bubble.
    character = BubbleCharacter(
        None,
        screen="bubble",
        window_style="bubble_window",
        who_style="bubble_who",
        what_style="bubble_what",
        _open_db=False)


init 1050 python hide:
    import json

    for k in sorted(bubble.properties):
        if k not in bubble.properties_order:
            bubble.properties_order.append(k)

    if config.developer:
        for k, v in bubble.properties.items():
            for i in v:
                try:
                    json.dumps(i)
                except:
                    raise Exception("bubble.properties[{!r}] contains a value that can't be serialized to JSON: {!r}".format(k, i))


screen _bubble_editor():
    zorder 1050

    drag:
        draggable True
        focus_mask None
        xpos 0
        ypos 0

        frame:
            style "empty"
            background "#0004"
            xpadding 5
            ypadding 5
            xminimum 150

            vbox:
                hbox:
                    spacing gui._scale(5)

                    text _("Speech Bubble Editor"):
                        style "_default"
                        color "#fff"
                        size gui._scale(14)

                    textbutton _("(hide)"):
                        style "_default"
                        action Hide()
                        text_color "#ddd"
                        text_hover_color "#fff"
                        text_size gui._scale(14)

                null height gui._scale(5)

                for image_tag, properties in bubble.GetCurrentDialogue():

                    hbox:
                        spacing gui._scale(5)

                        text "[image_tag!q]":
                            style "_default"
                            color "#fff"
                            size gui._scale(14)

                        for prop, action in properties:
                            textbutton "[prop!q]":
                                style "_default"
                                action action
                                alternate action.alternate
                                text_color "#ddd8"
                                text_selected_idle_color "#ddd"
                                text_hover_color "#fff"
                                text_size gui._scale(14)


screen _bubble_window_area_editor(action):
    modal True
    zorder 1051

    areapicker:
        cols bubble.cols
        rows bubble.rows

        finished action.finished

        add "#f004"

    key "game_menu" action Hide()
