# eagle2fritzing-python

This is a Python alternative to the [original eagle2fritzing](https://github.com/fritzing/eagle2fritzing). The original tool is writte in C++ and Qt, as well Qt XML Patterns Library is outdated -- after Qt 5.15.x, the library is no longer supported. Versions >Qt 6.5.3 no longer install XML Patterns. The code requires <Qt 6.5.3, so in the long run, if the [Fritzing](https://fritzing.org) devs don't maintain it, the code will be outdated and unusable. Additionally, Eagle is phasing out in June 2026, so the original code has to be changed.

My version of the tool uses the Python `lxml` library, so be sure to do

```bash
pip install lxml
```

## Contribute

If you're interested, please open a PR if you're a coder, or open issues. You can even contribute by starrung the repository!
