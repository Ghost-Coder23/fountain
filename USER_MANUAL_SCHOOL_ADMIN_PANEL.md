# User Manual — School Admin Panel

## 1) Purpose
The **School Admin Panel** is the administrative workspace for school staff with the **School Admin** role. From this panel, you can:
- View key school overview metrics.
- Manage users (add, edit, activate/deactivate).
- Update school branding and grading configuration.
- Enable/disable parent self-registration and manage the registration QR/link.

---

## 2) Sign in and open the Admin Panel
1. Sign in to your school portal (your subdomain).
2. In the left sidebar, open **Admin Panel** (the label shown under the Dashboard area).

---

## 3) School Admin Dashboard (Overview)
When you open the Admin Panel, you will typically see:

### 3.1 KPI tiles / summary cards
You’ll see counts such as:
- Students
- Teachers
- Parents
- Classes
- School Users
- Student/Teacher ratio (or capacity indicator)

### 3.2 Quick Actions
Use the action buttons/tiles to jump to common admin workflows, such as:
- **Enroll Student**
- **Add Teacher**
- **Add Class**
- **Add Subject**
- **Create Invoice**
- **Bulk Invoices**
- **Record Payment**
- **Payment Config**
- **Attendance Report**
- **Results & Grades**
- **Notifications**

✅ **Tip:** If you don’t see a menu item, confirm your account role is **School Admin**.

### 3.3 School Health / status blocks
The dashboard also shows operational health metrics like:
- Attendance completion today
- Total invoiced and collected
- Outstanding balances
- Overdue invoices

---

## 4) User Management
The **User Management** area lets you control who can access the school system.

### 4.1 Open User Management
1. From the Admin Dashboard, click **Manage Users**.
2. Or open the page directly via the left navigation/menu if available.

### 4.2 Understand the Users table
The table lists each user with:
- **Name**
- **Email**
- **Role** (badge)
- **Status** (Active / Inactive)
- **Actions** (Edit / Deactivate)

### 4.3 Add a user
1. Click **Add User**.
2. Complete the form fields:
   - **First Name**
   - **Last Name**
   - **Email Address**
   - **Role** (select one):
     - School Admin
     - Teacher
     - Student
     - Parent
3. Click **Add User**.

**Image placeholder (required):** Screenshot of the **Add User modal** (include role dropdown and submit button).
- Image filename suggestion: `user-management-add-user-modal.png`

✅ If the email already belongs to an existing platform user, it will be linked to your school (if not already linked). 

### 4.4 Edit user details
1. In the Actions column, click the **edit (pencil)** icon.
2. Update:
   - **First Name**
   - **Last Name**
   - **Email**
   - **Role**
   - **Status** (active/inactive)
3. Click **Save Changes**.

**Image placeholder (required):** Screenshot of the **Edit User** page.
- Image filename suggestion: `user-management-edit-user-page.png`

### 4.5 Deactivate (or reactivate) a user
1. In the Actions column, click the **trash/deactivate** button.
2. Confirm the prompt.

The system toggles the user’s **is_active** status:
- If currently **Active**, it becomes **Inactive**.
- If currently **Inactive**, it can be reactivated.

---

## 5) Settings (Branding, Grading, Parent Registration)
Open **Settings** from the left sidebar.

### 5.1 Branding & Theme
Update the visual identity of your school portal:
- **School Logo**: upload an image
- **Theme Color**: choose a color
- **School Motto**: set a short motto/tagline

**Image placeholder (required):** Screenshot of the **School Settings** branding fields.
- Image filename suggestion: `settings-branding-fields.png`
- **Logo image type needed:** image file (e.g., PNG/JPG)

### 5.2 Grading Configuration
You can configure how student grades are calculated.

1. Select **Grading System**.
2. If applicable (custom weights): set
   - **Continuous Assessment (CA) Weight (%)**
   - **Exam Weight (%)**

**Rule:** In the custom weights configuration, the **CA + Exam total must equal 100%**.

**Image placeholder (required):** Screenshot showing grading system dropdown and weight inputs.
- Image filename suggestion: `settings-grading-weights.png`

### 5.3 Upload your signature
1. In Settings, click **Upload Your Signature**.
2. Upload your signature image.
3. Click **Upload**.

**Image placeholder (required):** Screenshot of the **Upload Signature** page.
- Image filename suggestion: `settings-upload-signature.png`
- **Signature image type needed:** image file (e.g., PNG/JPG)

### 5.4 Parent Registration Portal (QR and links)
This feature controls whether parents can self-register and link their accounts to students.

---

## 8) Gallery / Media uploads (images and videos)
Some admin areas (like the school/platform gallery) may let you manage showcase media.

### 8.1 Local image upload
✅ **Local upload is supported** for images.

- The system uses: `GalleryItem.image` (an `ImageField`)

**Image placeholder (required):** Screenshot of the Gallery form showing the **image upload** field.
- Image filename suggestion: `gallery-image-upload-field.png`

### 8.2 Local video upload
❌ **Local video upload is not supported in the current system design.**

- The system stores videos as URLs using: `GalleryItem.video_url` (`URLField`)
- Result in Django Admin: you can provide a **video link**, but you cannot upload a video file.

**Image placeholder (required):** Screenshot of the Gallery form showing the **video URL** input field.
- Image filename suggestion: `gallery-video-url-field.png`

#### Want local video upload?
To support local video files, the code would need to be extended with a **file/video field** (e.g., `FileField`/`VideoField`) plus migrations, then the admin/form needs to expose that new upload field.

---



You can:
- Enable or disable parent self-registration.
- View/download the QR code.
- Copy the registration link.
- Regenerate the token (invalidates existing QR codes/links).

#### 5.4.1 Enable/Disable Registration
1. Find the **Parent Registration Portal** section.
2. Use the button:
   - **Enable Registration** (if disabled)
   - **Disable Registration** (if enabled)

**Image placeholder (required):** Screenshot of the **Parent Registration Portal enabled state**.
- Image filename suggestion: `settings-parent-registration-enabled.png`

#### 5.4.2 Download QR code
When registration is enabled:
1. Click **Download QR**.
2. Save the image.

#### 5.4.3 Copy registration link
1. Click **Copy Link**.
2. Paste the link into WhatsApp/email/printed handout.

**Image placeholder (required):** Screenshot showing QR, “Download QR”, and “Copy Link”.
- Image filename suggestion: `settings-parent-registration-qr-and-link.png`

#### 5.4.4 Regenerate QR/token
If you suspect QR links were shared beyond intended users:
1. Click **Regenerate QR**.
2. Confirm the warning.

This generates a new token, making older QR codes/links invalid.

**Image placeholder (required):** Screenshot of the “Regenerate QR” button and confirmation message.
- Image filename suggestion: `settings-regenerate-qr.png`

---

## 6) Common issues
- **Cannot add a user:** verify the email format and role selection. If the email already exists and is linked, the system may warn you.
- **Grading weights error:** ensure CA weight + Exam weight = **100%** when using custom weights.
- **Parent registration not working:** confirm parent registration is **enabled** and that parents are using a valid QR/link.

---

## 7) Recommended workflow checklist (Admin)
1. Add/activate staff users (teachers/admins).
2. Configure grading settings.
3. Upload admin signature.
4. Enable parent registration when admissions are open.
5. Monitor invoices, attendance, and announcements from the dashboard.

