# Verto PWA push notifications

This release adds standards-based Web Push for the installed Verto PWA. It sends:

- submitted Shift Assignment notifications to the linked Employee user;
- Task and supported mobile-form assignment notifications from new open ToDo records;
- Raven project-chat notifications to enabled users allocated through open ToDo assignments on Tasks in that Project.

The Raven message author is excluded. Chat notification bodies do not include message content or project names on the lock screen.

## 1. Install the Python dependency

From the bench directory:

```bash
./env/bin/pip install -r apps/verto/requirements.txt
```

`pywebpush` includes `py-vapid`, which provides the VAPID key utility.

## 2. Generate one VAPID key pair for the site

Create the keys outside the repository and keep the private key readable only by the bench user. The following example uses the site's private directory:

```bash
mkdir -p sites/dashboard.minesitesupport.com.au/private/verto-push
cd sites/dashboard.minesitesupport.com.au/private/verto-push
../../../../env/bin/vapid --gen
../../../../env/bin/vapid --applicationServerKey
```

The last command prints the base64url public application-server key. Save that output for the next step. Do not commit `private_key.pem`.

## 3. Configure the site

Return to the bench directory and set:

```bash
bench --site dashboard.minesitesupport.com.au set-config verto_push_vapid_public_key "PASTE_APPLICATION_SERVER_KEY"
bench --site dashboard.minesitesupport.com.au set-config verto_push_vapid_private_key "/ABSOLUTE/PATH/TO/private_key.pem"
bench --site dashboard.minesitesupport.com.au set-config verto_push_vapid_subject "mailto:support@webwire.com.au"
```

The private-key setting may be an absolute PEM file path or the PEM value itself. A file path is easier to rotate and keeps the key out of command history.

Do not replace the VAPID key pair after users subscribe. Changing it invalidates existing browser subscriptions and users will need to enable notifications again.

## 4. Build, migrate and restart

```bash
bench build --app verto
bench --site dashboard.minesitesupport.com.au migrate
bench restart
```

The frontend build copies the generated Workbox service worker to:

```text
apps/verto/verto/public/pwa/verto-mobile-sw.js
```

## 5. Serve the service worker at the PWA scope

Add `deploy/nginx_verto_service_worker_location.conf` inside the site's HTTPS server block, adjust the bench path if needed, test the Nginx configuration, and reload Nginx.

The browser must receive all of the following for `/verto-mobile-sw.js`:

- HTTP 200;
- `Content-Type: application/javascript`;
- `Service-Worker-Allowed: /verto-mobile/`;
- `Cache-Control: no-cache, no-store, must-revalidate`.

## 6. Verify

1. Open the installed Verto PWA while online.
2. Tap **Enable notifications** in the in-app prompt.
3. In a logged-in browser session, call `verto.api.mobile.push_notifications.send_test_push_notification` or create one of the supported allocation events.
4. Confirm a `Verto Push Subscription` record exists for the user and that `Last Successful Delivery` updates.
5. Tap a notification and confirm it opens the target shift, form, home, or Raven channel.

On iPhone and iPad, the user must first add Verto to the Home Screen and open that installed app before iOS will allow the notification permission request.

## PWA release updates

The installed PWA registers `/verto-mobile-sw.js` with `updateViaCache: none`. It checks for a new worker:

- shortly after app startup;
- whenever the app returns to the foreground;
- when network connectivity returns;
- every 15 minutes while open.

The new worker activates immediately and the current PWA reloads once when its controller changes. Users do not need to delete the PWA or its bookmark to receive frontend releases.
