from PyQt5.QtCore import pyqtSignal, QObject
import pickle
import weakref


def _attrForNotification(name):
    attr = name[6:-7].lower()
    if attr == "contours":
        attr = "_" + attr
    return attr


def _setGlyphContent(glyph, attr, value):
    data = pickle.loads(value)
    glyph.holdNotifications()
    if attr == "_contours":
        glyph.clearContours()
        shallow = data and "pen" not in data[0]  # XXX: flimsy
        if shallow:
            glyph._shallowLoadedContours = data
        else:
            for element in data:
                contour = glyph.instantiateContour()
                contour.setDataFromSerialization(element)
                glyph.appendContour(contour)
    elif attr == "components":
        glyph.clearComponents()
        for element in data:
            component = glyph.instantiateComponent()
            component.setDataFromSerialization(element)
            glyph.appendComponent(component)
    elif attr == "anchors":
        glyph.clearAnchors()
        for element in data:
            anchor = glyph.instantiateAnchor()
            anchor.setDataFromSerialization(element)
            glyph.appendAnchor(anchor)
    elif attr == "guidelines":
        glyph.clearGuidelines()
        for element in data:
            guideline = glyph.instantiateGuideline()
            guideline.setDataFromSerialization(element)
            glyph.appendGuideline(guideline)
    elif attr == "image":
        image = glyph.instantiateImage()
        image.setDataFromSerialization(data)
        glyph.image = image
    glyph.releaseHeldNotifications()

# TODO: limit the number of elements


class UndoManager(QObject):
    canUndoChanged = pyqtSignal(bool)
    canRedoChanged = pyqtSignal(bool)
    # undoTextChanged = pyqtSignal(str)
    # redoTextChanged = pyqtSignal(str)

    def __init__(self, glyph):
        super().__init__()
        self._glyph = weakref.ref(glyph)
        self._undoStack = []
        self._redoStack = []
        self._cleanIndex = 0
        self._dumps = dict()
        self._groupNotifications = dict()
        self._groupUndo = 0

        self._valueNotifications = n = dict()
        n["Glyph.NameChanged"] = self.tr("Name changed.")
        n["Glyph.UnicodesChanged"] = self.tr("Unicode(s) changed.")
        n["Glyph.WidthChanged"] = self.tr("Width changed.")
        n["Glyph.HeightChanged"] = self.tr("Height changed.")
        n["Glyph.NoteChanged"] = self.tr("Note changed.")
        self._contentNotifications = n = dict()
        n["Glyph.ContoursChanged"] = self.tr("Contours changed.")
        n["Glyph.ComponentsChanged"] = self.tr("Components changed.")
        n["Glyph.AnchorsChanged"] = self.tr("Anchors changed.")
        n["Glyph.GuidelinesChanged"] = self.tr("Guidelines changed.")
        n["Glyph.ImageChanged"] = self.tr("Image changed.")

        self._subscribeToGlyph()

    def _subscribeToGlyph(self):
        glyph = self.glyph
        for name in self._valueNotifications.keys():
            glyph.addObserver(self, "_valueChanged", name)
        for name in self._contentNotifications.keys():
            attr = _attrForNotification(name)
            data = None
            if attr == "_contours":
                data = getattr(glyph, "_shallowLoadedContours", None)
            elif attr == "image":
                data = getattr(glyph, attr).getDataForSerialization()
            if data is None:
                data = [item.getDataForSerialization(
                    ) for item in getattr(glyph, attr)]
            self._dumps[name] = pickle.dumps(data)
            glyph.addObserver(self, "_contentChanged", name)

    def _unsubscribeFromGlyph(self):
        glyph = self.glyph
        for name in self._valueNotifications.keys():
            glyph.removeObserver(self, name)
        for name in self._contentNotifications.keys():
            glyph.removeObserver(self, name)
        self._dumps = dict()

    @property
    def glyph(self):
        if self._glyph is None:
            return None
        return self._glyph()

    # -------------
    # Notifications
    # -------------

    def _valueChanged(self, notification):
        name = notification.name
        data = notification.data
        if self._groupUndo:
            if name not in self._groupNotifications:
                self._groupNotifications[name] = data
            else:
                self._groupNotifications[name][
                    "newValue"] = data["newValue"]
        else:
            self._pushValueChange(name, data)

    def _contentChanged(self, notification):
        name = notification.name
        if self._groupUndo:
            self._groupNotifications[name] = None
        else:
            self._pushContentChange(name)

    # handlers

    def _pushValueChange(self, name, data):
        undoWasLocked = not self.canUndo()
        redoWasEnabled = self.canRedo()

        self._redoStack = []
        self._undoStack.append((name, data))
        if undoWasLocked:
            self.canUndoChanged.emit(True)
        if redoWasEnabled:
            self.canRedoChanged.emit(False)

    def _pushContentChange(self, name):
        glyph = self.glyph
        attr = _attrForNotification(name)
        if name not in self._dumps:
            oldValue = self._dumps["_shallowLoadedContours"]
            del self._dumps["_shallowLoadedContours"]
        else:
            oldValue = self._dumps[name]
        if attr == "image":
            data = getattr(glyph, attr).getDataForSerialization()
        else:
            data = [item.getDataForSerialization() for item in getattr(
                glyph, attr)]
        newValue = self._dumps[name] = pickle.dumps(data)
        data = dict(oldValue=oldValue, newValue=newValue)

        self._pushValueChange(name, data)

    # ----------
    # Public API
    # ----------

    def clear(self):
        raise NotImplementedError

    # basic API

    def beginUndoGroup(self, text=None):
        if not self._groupUndo:
            self._groupUndoText = text
        self._groupUndo += 1

    def endUndoGroup(self):
        if not self._groupUndo:
            print("warning: unmatched endUndoGroup()")
            return
        self._groupUndo -= 1
        if not self._groupUndo:
            if self._groupNotifications:
                undoStack = self._undoStack
                self._undoStack = group = []
                for name, data in self._groupNotifications.items():
                    if data is None:
                        self._pushContentChange(name)
                    else:
                        self._pushValueChange(name, data)
                self._groupNotifications = dict()
                self._undoStack = undoStack
                self._undoStack.append((self._groupUndoText, group))
            del self._groupUndoText

    def canUndo(self):
        return not self._groupUndo and bool(self._undoStack)

    def canRedo(self):
        return not self._groupUndo and bool(self._redoStack)

    def undo(self):
        if not self._undoStack or self._groupUndo:
            return
        glyph = self.glyph
        redoWasLocked = not self.canRedo()

        # pop the undo element
        content = self._undoStack.pop()
        if isinstance(content[1], list):
            elements = content[1]
        else:
            elements = (content,)
        for element in reversed(elements):
            # apply the old value
            name, data = element
            attr = _attrForNotification(name)
            value = data["oldValue"]
            glyph.disableNotifications(observer=self)
            if name in self._contentNotifications:
                _setGlyphContent(glyph, attr, value)
                self._dumps[name] = value
            else:
                setattr(glyph, attr, value)
            glyph.enableNotifications(observer=self)
        # push as redo element
        self._redoStack.append(content)

        if len(self._undoStack) == self._cleanIndex:
            glyph.dirty = False
        if redoWasLocked:
            self.canRedoChanged.emit(True)
        if not self.canUndo():
            self.canUndoChanged.emit(False)

    def redo(self):
        if not self._redoStack or self._groupUndo:
            return
        glyph = self.glyph
        undoWasLocked = not self.canUndo()

        # pop the redo element
        content = self._redoStack.pop()
        if isinstance(content[1], list):
            elements = content[1]
        else:
            elements = (content,)
        for element in elements:
            # apply the new value
            name, data = element
            attr = _attrForNotification(name)
            value = data["newValue"]
            glyph.disableNotifications(observer=self)
            if name in self._contentNotifications:
                _setGlyphContent(glyph, attr, value)
                self._dumps[name] = value
            else:
                setattr(glyph, attr, value)
            glyph.enableNotifications(observer=self)
        # push as undo element
        self._undoStack.append(content)

        if len(self._undoStack) == self._cleanIndex:
            glyph.dirty = False
        if undoWasLocked:
            self.canUndoChanged.emit(True)
        if not self.canRedo():
            self.canRedoChanged.emit(False)

    # clean

    def isClean(self):
        return self._cleanIndex == len(self._undoStack)

    def setClean(self):
        self._cleanIndex = len(self._undoStack)

    # text

    def undoText(self):
        name = self._undoStack[-1][0]
        if name in self._contentNotifications:
            return self._contentNotifications[name]
        return self._valueNotifications[name]

    def redoText(self):
        name = self._redoStack[-1][0]
        if name in self._contentNotifications:
            return self._contentNotifications[name]
        return self._valueNotifications[name]
