# Extension Icons

This directory should contain the extension icons in the following sizes:
- icon16.png (16x16 pixels)
- icon48.png (48x48 pixels)
- icon128.png (128x128 pixels)

For now, you can use placeholder icons or create custom ones.

## Quick Placeholder Icons

You can generate simple placeholder icons using ImageMagick:

```bash
# Install ImageMagick if needed
# macOS: brew install imagemagick
# Ubuntu: sudo apt-get install imagemagick

# Generate placeholder icons
convert -size 16x16 xc:#0366d6 -pointsize 10 -fill white -gravity center -annotate +0+0 "C" icon16.png
convert -size 48x48 xc:#0366d6 -pointsize 30 -fill white -gravity center -annotate +0+0 "C" icon48.png
convert -size 128x128 xc:#0366d6 -pointsize 80 -fill white -gravity center -annotate +0+0 "C" icon128.png
```

Or use any PNG images you prefer!
