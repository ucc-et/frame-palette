# Building a standalone app

This produces a double-clickable desktop app with no Python install required,
using [PyInstaller](https://pyinstaller.org/).

## 1. Install build dependencies

From a clean virtual environment, on the machine/OS you want to build for
(PyInstaller does not cross-compile -- build on macOS to get a `.app`, on
Windows to get a `.exe`, etc.):

```sh
pip install -e ".[dev]"
pip install pyinstaller
```

## 2. Build

```sh
pyinstaller frame_palette_app.spec
```

This bundles the engine, the FastAPI backend, the `ui/` frontend, and the
pywebview shell into a single artifact under `dist/`:

- **macOS**: `dist/FramePalette.app` (an app bundle with everything unpacked
  inside it, so each library can be code-signed in place -- see
  [Signing and notarizing the macOS app](#signing-and-notarizing-the-macos-app))
- **Windows**: `dist/FramePalette.exe` (one file, nothing else needed)
- **Linux**: `dist/FramePalette` (one file; `chmod +x` it if it isn't
  already executable)

`build/` and `dist/` are git-ignored -- rerun step 2 any time to rebuild;
delete both directories first for a fully clean build.

## 3. Run it

- **macOS**: double-click `dist/FramePalette.app`. An app you built yourself
  opens directly; Gatekeeper only checks copies that were *downloaded*
  (they carry a quarantine flag). For those, either sign and notarize the
  build (below) or follow the steps in the README's
  [Opening the app on macOS](README.md#opening-the-app-on-macos).
- **Windows/Linux**: run `dist/FramePalette.exe` / `dist/FramePalette`
  directly.

The app starts its own local backend on an unused port and opens a native
window pointed at it -- no terminal, no browser tab, no manual server step.

## Notes

- `frame_palette_app.spec` bundles `ui/` as a data directory and pulls in
  `numpy`, `opencv-python` (`cv2`), `Pillow`, `fastapi`, `uvicorn`, and
  `pywebview` (plus a few uvicorn hidden imports it only resolves at
  runtime) via `PyInstaller.utils.hooks.collect_all`.
- `bundle_identifier` in the spec (`com.ucc-et.frame-palette`) and `icon`
  (currently unset) are placeholders -- swap in a real reverse-DNS id and an
  `.icns`/`.ico` file if you want a custom app icon or plan to distribute
  the app more widely.

## Signing and notarizing the macOS app

A downloaded `.app` only opens without the *"Apple could not verify
'FramePalette' is free of malware"* block if it is signed with a
**Developer ID Application** certificate *and* notarized by Apple. There is
no free way around this: it requires a paid
[Apple Developer Program](https://developer.apple.com/programs/) membership.

Without a certificate, PyInstaller ad-hoc signs the app. It runs fine where
it was built, but every downloaded copy hits the warning above.

### One-time setup

1. **Create the certificate.** In Xcode -> Settings -> Accounts -> *Manage
   Certificates...*, click **+** -> **Developer ID Application** (or create
   it on [developer.apple.com](https://developer.apple.com/account/resources/certificates)).
2. **Export it.** In Keychain Access, find *Developer ID Application: <your
   name> (<TEAM ID>)*, right-click -> *Export...*, save as `.p12`, and set a
   password.
3. **Create an app-specific password** for notarization at
   [account.apple.com](https://account.apple.com) -> Sign-In and Security ->
   App-Specific Passwords.
4. **Find your Team ID** under Membership details on
   [developer.apple.com/account](https://developer.apple.com/account).
5. **Add these repository secrets** (GitHub -> Settings -> Secrets and
   variables -> Actions):

   | Secret | Value |
   | --- | --- |
   | `MACOS_CERTIFICATE_P12` | the `.p12` file, base64-encoded: `base64 -i cert.p12 \| pbcopy` |
   | `MACOS_CERTIFICATE_PASSWORD` | the password you set when exporting the `.p12` |
   | `APPLE_ID` | your Apple Account email |
   | `APPLE_APP_SPECIFIC_PASSWORD` | the app-specific password from step 3 |
   | `APPLE_TEAM_ID` | your 10-character Team ID |

The next release build then imports the certificate into a temporary
keychain, signs every binary with the hardened runtime
(`packaging/macos/entitlements.plist`), submits the zip to Apple's notary
service, staples the ticket to the `.app`, and checks it with `spctl`.
Without `MACOS_CERTIFICATE_P12` the build still succeeds unsigned, and the
release notes point macOS users at the manual workaround.

### Signing a local build

With the certificate in your login keychain:

```sh
MACOS_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
  pyinstaller frame_palette_app.spec
```

To notarize it by hand, zip it with
`ditto -c -k --keepParent dist/FramePalette.app FramePalette.zip`, run
`xcrun notarytool submit FramePalette.zip --apple-id ... --team-id ... --password ... --wait`,
then `xcrun stapler staple dist/FramePalette.app`.

## Automated releases

`.github/workflows/release.yml` runs this same build automatically for
macOS, Windows, and Linux every time a merge lands on `main` (not on pull
requests), and publishes the three archives as assets on a new GitHub
Release. It pins Python 3.11 for the build rather than whatever's newest --
see the comment in the workflow for why. If you push a version bump, it
shows up in the next release's tag (`v<version>-<run number>`). The macOS
build is signed and notarized when the secrets described above are set.
