# OpenChecklists End-to-End Human Test Script

**Date prepared:** 2026-08-11  
**Live site:** https://openchecklists.net  
**API base:** https://app.openchecklists.net/api  
**Zitadel auth:** https://auth.keylinkit.net  
**Tester email:** use a real mailbox you can access (e.g. your own Gmail)

Estimated time: 20–30 minutes for the full pass.  
Mark each step ✅ PASS or ❌ FAIL with any notes.

---

## Smoke checks (before you start)

Run these in a browser or terminal. They should pass before testing the UI.

| Check | URL | Expected |
|-------|-----|----------|
| Leaderboard API | https://app.openchecklists.net/api/leaderboard | `{"leaderboard":[...]}` (may be empty) |
| Auth required | https://app.openchecklists.net/api/me | `{"error":"Unauthorized"}` |
| Home page loads | https://openchecklists.net/ | Page loads, no JS errors |
| Profile page has clientId | https://openchecklists.net/profile | Page source contains `385717620558594052` |

---

## SECTION 1 — Self-registration (new user path)

Self-registration was enabled 2026-08-11. Use a **fresh email address** that has never logged in.

### 1.1 Trigger registration
1. Open https://openchecklists.net/profile in a private/incognito window
2. Click **Sign In** (or the sign-in button in the header)
3. You should be redirected to https://auth.keylinkit.net/...
4. On the Zitadel login page, click **"Register"** (should now be visible — was hidden before)  
   ✅ PASS if "Register" link appears  
   ❌ FAIL if no register option (self-registration may not have propagated)

### 1.2 Complete registration
1. Enter your email address in the registration form
2. Choose a display name / username if prompted
3. Click **Register** / **Continue**
4. Zitadel should send a **verification email** or go straight to OTP code entry  
   ✅ PASS if you receive an email within 2 minutes  
   ❌ FAIL if email never arrives (check spam; check Zitadel SMTP config)

### 1.3 Enter the OTP code
1. Open the email from Zitadel
2. Copy the 6-digit code (or click the magic link)
3. Enter it on the Zitadel page
4. You should be redirected to https://openchecklists.net/auth/callback.html, then to /profile  
   ✅ PASS if you land on /profile signed in  
   ❌ FAIL if you see an error like `COMMAND-JKLJ3` — the OTP-email factor wasn't auto-registered (check Worker logs)

---

## SECTION 2 — First login XP award

### 2.1 Profile shows points
1. On /profile, look for your points total
2. It should show **25 points** (first_login bonus)
3. Your level should be displayed (Level 1 at 0–99 pts)  
   ✅ PASS if 25 XP shown  
   ❌ FAIL if 0 XP or profile fails to load

### 2.2 Profile API direct check
In DevTools console (or a new tab):
```
fetch('https://app.openchecklists.net/api/me', {
  headers: { Authorization: 'Bearer ' + window._oclToken }
}).then(r=>r.json()).then(console.log)
```
If `window._oclToken` is undefined, try: `localStorage.getItem('ocl_token')` or check the page JS for the token.  
Expected: `{ "user_id": "...", "points": 25, "level": 1, ... }`  
✅ PASS if points=25  
❌ FAIL if error or points=0

---

## SECTION 3 — Add aircraft (+15 XP)

### 3.1 Add your aircraft
1. On /profile, find the **My Aircraft** section
2. Click **Add Aircraft**
3. Enter make: `ParaPlane`, model: `PM-2`, year: `2020` (or whatever you fly)
4. Save  
   ✅ PASS if aircraft appears in your list  
   ❌ FAIL if save fails or aircraft doesn't appear

### 3.2 Verify XP increase
1. Refresh the profile page
2. Points should now show **40** (25 + 15)  
   ✅ PASS if 40 XP shown  
   ❌ FAIL if still 25

---

## SECTION 4 — Airport star save (+0 XP, but tests the hook)

### 4.1 Visit an airport page
1. Navigate to https://openchecklists.net/airports/KSFO (or any airport code you know)
2. The page should load showing airport details  
   ✅ PASS if page loads with airport info  
   ❌ FAIL if blank or error

### 4.2 Save/star the airport
1. Look for a **★ Save** button or star icon on the airport page
2. Click it — you should see a confirmation (toast or button state change)
3. Navigate to /profile → My Airports — your airport should appear  
   ✅ PASS if airport shows in profile  
   ❌ FAIL if star doesn't respond or airport doesn't save

---

## SECTION 5 — Training quiz (+3 XP per correct answer)

### 5.1 Open training page
1. Navigate to https://openchecklists.net/training
2. Page should show training resources and a quiz section  
   ✅ PASS if page loads  
   ❌ FAIL if blank or error

### 5.2 Answer a quiz question correctly
1. Find a quiz question and select the correct answer
2. Submit
3. Look for XP notification or toast showing +3 points  
   ✅ PASS if XP notification appears  
   ❌ FAIL if no feedback or error

### 5.3 Verify XP after quiz
1. Check profile or run `/api/me` — points should be 43 (40 + 3)
2. Answer a second question — should go to 46  
   ✅ PASS if points increment by 3 each correct answer  
   ❌ FAIL if XP doesn't change

---

## SECTION 6 — Checklist and preflight log (+10 XP for complete)

### 6.1 Open a checklist
1. Navigate to https://openchecklists.net/c/ or the checklist library
2. Find a checklist (e.g. a generic preflight checklist)
3. Open it and check off all items  
   ✅ PASS if checklist renders and items are checkable  
   ❌ FAIL if page blank or items unresponsive

### 6.2 Email the log
1. After completing the checklist, click **Email me this log** button
2. Enter your email address and submit
3. Check your inbox for the log email  
   ✅ PASS if email arrives within 5 minutes  
   ❌ FAIL if no email (check spam)

### 6.3 Verify preflight_complete XP
1. Completing and emailing a full checklist awards **10 XP** (preflight_complete) + **5 XP** (first_of_day)
2. Check profile — points should have increased by 15  
   ✅ PASS if points went up by 15  
   ❌ FAIL if unchanged

---

## SECTION 7 — Leaderboard opt-in

### 7.1 Enable leaderboard display
1. On /profile, find the **Leaderboard** toggle or opt-in setting
2. Enable it (may require setting a display name first)
3. Save  
   ✅ PASS if setting saves without error  
   ❌ FAIL if save fails

### 7.2 Verify you appear on leaderboard
1. Open https://app.openchecklists.net/api/leaderboard in a new tab
2. Your username/display_name should appear  
   ✅ PASS if your name is in the leaderboard JSON  
   ❌ FAIL if absent (check that display_name is set and share_leaderboard=true via /api/me)

---

## SECTION 8 — Sign out and sign back in (returning user path)

### 8.1 Sign out
1. On /profile, find the **Sign Out** button
2. Click it — you should return to the signed-out state  
   ✅ PASS if profile shows "Sign In" button again  
   ❌ FAIL if you stay signed in or page errors

### 8.2 Sign back in (returning user — no registration form)
1. Click **Sign In**
2. Enter your email address on Zitadel login page
3. Zitadel should NOT show "Register" form for a known user — just email + OTP
4. Receive OTP code by email and enter it
5. Return to /profile signed in  
   ✅ PASS if login completes without the registration form  
   ❌ FAIL if you're prompted to register again

### 8.3 Points preserved
1. Your points total from earlier should still be there (no reset on re-login)
2. No additional first_login bonus should have been awarded  
   ✅ PASS if same point total from end of Section 7  
   ❌ FAIL if points reset or extra first_login bonus

---

## SECTION 9 — API smoke tests (DevTools)

Open the browser DevTools console on any page of openchecklists.net while signed in.

```javascript
// Test 1: Profile
oclReq('/api/me').then(r=>r.json()).then(d => console.log('Profile:', d))

// Test 2: Airports
oclReq('/api/me/airports').then(r=>r.json()).then(d => console.log('Airports:', d))

// Test 3: Aircraft
oclReq('/api/me/aircraft').then(r=>r.json()).then(d => console.log('Aircraft:', d))

// Test 4: Training
oclReq('/api/me/training').then(r=>r.json()).then(d => console.log('Training:', d))

// Test 5: Logs
oclReq('/api/me/logs').then(r=>r.json()).then(d => console.log('Logs:', d))
```

Each should return a 200 JSON response with your data, no errors.  
✅ PASS all 5  
❌ FAIL if any returns `{"error":"Unauthorized"}` while signed in — token refresh may be broken

---

## SECTION 10 — Sign-in from content pages

### 10.1 Training page sign-in hook
1. Sign out first
2. Navigate to https://openchecklists.net/training
3. Without signing in, click a quiz answer
4. You should see a **"Sign in to save progress"** prompt or be redirected to login  
   ✅ PASS if prompt appears  
   ❌ FAIL if XP is silently dropped without prompt

### 10.2 Airport page sign-in hook
1. While signed out, visit an airport page
2. Click the **★ Save** button
3. Should prompt to sign in (not silently fail)  
   ✅ PASS if sign-in prompt appears  
   ❌ FAIL if star click does nothing

---

## Summary table

| Section | Feature | Result | Notes |
|---------|---------|--------|-------|
| 1 | Self-registration | | |
| 2 | First login XP (+25) | | |
| 3 | Add aircraft XP (+15) | | |
| 4 | Airport star save | | |
| 5 | Quiz XP (+3 each) | | |
| 6 | Preflight log XP (+10+5) | | |
| 7 | Leaderboard opt-in | | |
| 8 | Sign out / returning user | | |
| 9 | API smoke tests | | |
| 10 | Sign-in hooks on content pages | | |

---

## Known issues to watch for

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `COMMAND-JKLJ3` on login | OTP email factor not auto-registered | Should be fixed — worker calls `ensureOtpEmail()` on first `/api/me` |
| No "Register" link on Zitadel page | Self-registration disabled | Now enabled at both org and instance level (2026-08-11) |
| `/api/me` returns 401 after successful Zitadel login | PKCE callback URL mismatch | Redirect URI must be exactly `https://openchecklists.net/auth/callback.html` |
| Points not updating | D1 database issue or Worker not deployed | Check `curl https://app.openchecklists.net/api/me` with auth header |
| Email never arrives | Zitadel SMTP not configured | Check Zitadel SMTP settings in admin console |

---

## Quick links for debugging

```bash
# Check API is live
curl https://app.openchecklists.net/api/leaderboard

# Check profile page has right client ID
curl -sL https://openchecklists.net/profile | grep 385717620558594052

# Check auth callback page exists
curl -sI https://openchecklists.net/auth/callback.html
```
