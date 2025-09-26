## GEMS Runner
### Graphical Environment Management System
Travis L. Seymour, PhD

NOTE: on Linux, you may need to issue additional tools:

E.g., if you get this message:

```
qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.
```

then issue this command:

```bash
sudo apt-get install libxcb-cursor0
```

---

If sound isn't working on Linux, try this:

```bash
sudo dnf install gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good \
                 gstreamer1-plugins-bad-free gstreamer1-plugins-bad-freeworld \
                 gstreamer1-plugins-ugly gstreamer1-libav
```
