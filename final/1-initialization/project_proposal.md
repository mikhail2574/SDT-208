# Project Title

TestHub - Online Quiz & Assessment Platform

---

## Brief Description of the Application

TestHub is a web application for creating, managing, and taking online tests and quizzes.  
The main goal is to provide a simple but robust platform where:

- **Test authors** can design structured tests with different types of questions.
- **Regular users** can take these tests and see detailed results and feedback.
- **Administrators** can manage users and moderate the content.

This application addresses the need for lightweight assessment tools for small teams, courses, and internal training.  
Target users:

- University students and instructors
- Small training centers
- Companies that need internal knowledge checks or onboarding quizzes

---

## Key Features

1. **User Registration & Authentication**

   - Sign up / log in with email + password
   - Basic profile (name, email, active status)
   - Password stored as a secure hash

2. **Role-Based Access Control**

   - **Admin**: manage users, roles, and global settings; can deactivate users and remove inappropriate tests.
   - **Author**: create, edit, publish and unpublish tests; see statistics for own tests.
   - **Test Taker (Regular User)**: browse available tests and take them; view own attempt history and scores.

3. **Test Management (CRUD for Tests and Questions)**

   - Create tests with:
     - Title, description, difficulty level
     - Optional time limit
   - Add questions to a test:
     - Single-choice, multiple-choice, or free-text question types
   - Manage answer options for choice-based questions
   - Mark correct answers and assign points per question
   - Publish / unpublish tests (only published tests are visible to regular users)

4. **Taking Tests & Scoring**

   - Start a test attempt with a timer if a time limit is defined
   - Navigate through questions during an attempt
   - Store all user answers for each attempt
   - Automatic scoring for choice-based questions
   - Store the final score and attempt details (start/end time, status)

5. **Results & Dashboard**
   - For test takers:
     - List of previous attempts with scores and timestamps
     - Detailed view of a single attempt (which answers were correct/incorrect)
   - For authors:
     - List of tests they created
     - Basic statistics per test (number of attempts, average score)
   - For admins:
     - Overview of user list, active/inactive status
     - Overview of total number of tests and attempts

---

## User Roles

### 1. Admin

- Manage users (activate/deactivate accounts)
- Assign or remove roles (e.g., grant "Author" permissions)
- View system-wide statistics (number of users, tests, attempts)
- Optionally delete or hide tests that violate policy

### 2. Author

- Create, edit, and delete own tests
- Add questions and answer options to their tests
- Publish/unpublish their tests
- View statistics for their tests (attempt count, average score)
- Cannot modify users or tests created by other authors

### 3. Test Taker (Regular User)

- Register, log in, and update basic profile data
- Browse and filter published tests
- Start test attempts and submit answers
- See own history of attempts and scores
- No access to test editing or user management

---

## Page Structure

Planned main pages/views:

1. **Home / Landing Page**

   - Short description of the platform
   - Links to login and registration

2. **Authentication Pages**

   - **Login Page** - email + password
   - **Registration Page** - create new account

3. **User Dashboard**

   - For test takers: list of available tests and own attempts
   - For authors: "My Tests" list + quick stats
   - For admins: system overview (users, tests, attempts)

4. **Test Catalog Page**

   - List of all published tests available to the current user
   - Basic filters (e.g., by difficulty)

5. **Test Details Page**

   - Test title, description, difficulty, estimated duration
   - "Start Test" button

6. **Test Taking Page**

   - Full-screen view of questions
   - Timer (if test has a time limit)
   - Navigation between questions
   - Submit attempt

7. **Attempt Result Page**

   - Final score and maximum possible score
   - For each question: user's answer vs correct answer (for auto-gradable types)

8. **Author Pages**

   - **My Tests List** - CRUD for tests
   - **Test Edit Page** - edit test info
   - **Question Management Page** - add/edit/remove questions and answer options
   - **Test Statistics Page** - summary stats per test

9. **Admin Pages**
   - **User Management Page** - list of users, roles and active status
   - **System Stats Page** - counts of users, tests, and attempts

This structure is modular and can be expanded later if needed (e.g., categories/tags, more analytics).
