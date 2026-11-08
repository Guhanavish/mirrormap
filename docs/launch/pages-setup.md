# Publish the MirrorMap landing page with GitHub Pages

The repository now has a dedicated **`gh-pages`** branch containing the original static MirrorMap landing page. **The site is not live until the repository owner enables GitHub Pages.**

1. Open [Repository Settings → Pages](https://github.com/Guhanavish/mirrormap/settings/pages).
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch **`gh-pages`**, directory **`/(root)`**, and save.
4. Confirm that the Pages deployment succeeds in the Actions tab. The expected GitHub Pages address is `https://guhanavish.github.io/mirrormap/` **after activation**.
5. Open the site and check the installation and documentation buttons. Only then add it to the repository's About homepage.

The `gh-pages` branch holds static documentation **only**; it is not a hosted interactive audit engine, and no repository code or user projects are uploaded through the landing page.

To update the site, edit `site/index.html` on `main`, review and validate it, then update the `gh-pages` branch's root `index.html`. Pages settings are repository administration controls and cannot be changed through the current limited content-only GitHub connector.
