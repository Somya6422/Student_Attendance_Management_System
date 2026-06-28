# 🎓 Student Attendance Management System

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green)
![SQLite](https://img.shields.io/badge/Database-SQLite-blue)
![License](https://img.shields.io/badge/License-GPL--3.0-red)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

A desktop-based Student Attendance Management System developed using **Python**, **Tkinter**, and **SQLite**.

The application enables teachers, students, and principals to manage attendance efficiently through manual attendance, QR Code-based attendance, attendance analytics, and student performance monitoring.

---

## Features

- 👨‍🏫 Teacher Portal
- 👨‍🎓 Student Portal
- 👔 Principal Portal
- 📷 QR Code Attendance
- 📊 Attendance Analytics
- 📈 Pie Chart Reports
- 🔐 Secure Login System
- 🗄 SQLite Database
- 🔔 Notification System
- ⚠ Attendance Warning Alerts
- 🌐 Local Web Attendance Portal
- 🖥 Desktop GUI using Tkinter

---

## Technologies Used

- Python
- Tkinter
- SQLite
- Pillow
- qrcode
- tkcalendar
- hashlib
- HTTP Server
- Threading

---

# 📸 Application Screenshots

<h2 align="center">Login Screen</h2>

![Login](assets/screenshots/login.png)

---

<h2 align="center">Teacher Dashboard</h2>

### Add Student

![Teacher Add Student](assets/screenshots/teacher_dashboard_add_student.png)

### Mark Attendance Manually

![Teacher Attendance](assets/screenshots/teacher_dashboard_mark_attendance_manually.png)

### QR Attendance

![QR Attendance](assets/screenshots/teacher_QR_attendance.png)

### Notifications

![Notifications](assets/screenshots/teacher_dashboard_notifications.png)

---

<h2 align="center">Student Dashboard</h2>

![Student Dashboard](assets/screenshots/student_dashboard.png)

### Student Messages

![Student Messages](assets/screenshots/student_dashboard_message.png)

---

<h2 align="center">Principal Dashboard</h2>

### Actions

![Principal Action](assets/screenshots/principal_action.png)

### Attendance Analytics

![Pie Chart](assets/screenshots/principal_dashboard_pie_chart.png)

### Reports

![Reports](assets/screenshots/principal_dashboard_reports.png)

### Messages

![Principal Message](assets/screenshots/principal_message.png)

---

# 🚀 Installation

## Clone the Repository

```bash
git clone https://github.com/Somya6422/Student_Attendance_Management_System.git
```

## Navigate to the Project Folder

```bash
cd Student_Attendance_Management_System
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Run the Application

```bash
python "Source Code.py"
```

---

# 📂 Project Structure

```
Student_Attendance_Management_System/
│
├── assets/
│   └── screenshots/
├── dist/
│   ├── Source Code.exe
│   └── attendance.db
├── Source Code.py
├── attendance.db
├── requirements.txt
├── README.md
└── LICENSE
```

---

# 👥 User Roles

### 👨‍🏫 Teacher

- Login securely
- Add students
- Mark attendance manually
- Generate QR Code attendance
- View notifications

### 👨‍🎓 Student

- Login
- View attendance percentage
- Receive attendance warnings
- View notifications

### 👔 Principal

- View attendance analytics
- Generate reports
- Send announcements
- Monitor overall attendance

---

# 🔮 Future Improvements

- Export reports to PDF
- Export attendance to Excel
- Email notifications
- Cloud database support
- Mobile application
- Face Recognition Attendance
- RFID/Fingerprint Attendance
- Multi-school support

---

# 🤝 Contributing

Contributions, suggestions, and bug reports are welcome.

If you find any issue, feel free to open an issue or submit a pull request.

---

# 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

See the LICENSE file for details.
