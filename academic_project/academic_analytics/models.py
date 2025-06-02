from django.db import models

class Department(models.Model):
    dept_id = models.AutoField(primary_key=True)
    dept_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'department'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return self.dept_name

class Student(models.Model):
    stu_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    gender = models.CharField(max_length=10)
    dob = models.DateField()
    dept = models.ForeignKey(Department, on_delete=models.CASCADE, db_column='dept_id')  # Menentukan nama kolom foreign key

    class Meta:
        db_table = 'student'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return self.name

class Course(models.Model):
    course_id = models.AutoField(primary_key=True)
    course_name = models.CharField(max_length=100)
    dept = models.ForeignKey(Department, on_delete=models.CASCADE, db_column='dept_id')

    class Meta:
        db_table = 'course'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return self.course_name

class Instructor(models.Model):
    instructor_id = models.AutoField(primary_key=True)
    instructor_name = models.CharField(max_length=100)
    dept = models.ForeignKey(Department, on_delete=models.CASCADE, db_column='dept_id')

    class Meta:
        db_table = 'instructor'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return self.instructor_name

class Semester(models.Model):
    semester_id = models.AutoField(primary_key=True)
    semester_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'semester'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return self.semester_name

class Enrollment(models.Model):
    enroll_id = models.AutoField(primary_key=True)
    stu = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='stu_id')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, db_column='course_id')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, db_column='semester_id')
    grade = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'enrollment'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return f"{self.stu.name} - {self.course.course_name}"

class Assessment(models.Model):
    assessment_id = models.AutoField(primary_key=True)
    enroll = models.ForeignKey(Enrollment, on_delete=models.CASCADE, db_column='enroll_id')
    assessment_type = models.CharField(max_length=50)
    score = models.IntegerField()

    class Meta:
        db_table = 'assessment'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return f"{self.enroll.stu.name} - {self.enroll.course.course_name} - {self.assessment_type}"

class Attendance(models.Model):
    attendance_id = models.AutoField(primary_key=True)
    enroll = models.ForeignKey(Enrollment, on_delete=models.CASCADE, db_column='enroll_id')
    attendance_percentage = models.IntegerField()

    class Meta:
        db_table = 'attendance'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return f"{self.enroll.stu.name} - {self.enroll.course.course_name} - {self.attendance_percentage}%"

class CourseDifficulty(models.Model):
    course = models.OneToOneField(Course, primary_key=True, on_delete=models.CASCADE, db_column='course_id')
    difficulty_level = models.CharField(max_length=50)

    class Meta:
        db_table = 'course_difficulty'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return f"{self.course.course_name} - {self.difficulty_level}"

class CourseInstructor(models.Model):
    course_instructor_id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, db_column='course_id')
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, db_column='instructor_id')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, db_column='semester_id')

    class Meta:
        db_table = 'course_instructor'  # Ganti dengan nama tabel yang sebenarnya di database Anda

    def __str__(self):
        return f"{self.course.course_name} - {self.instructor.instructor_name}"
    
class ModelStandy(models.Model):
    model_name = models.CharField(max_length=100)
    model_file = models.CharField(max_length=255)
    training_data = models.CharField(max_length=255)
    training_date = models.DateTimeField()
    model_summary = models.TextField(blank=True)

    def __str__(self):
        return f"{self.model_name} - {self.training_date.strftime('%Y-%m-%d')}"
    
class ModelInsan(models.Model):
    model_name = models.CharField(max_length=100)
    model_file = models.CharField(max_length=255)
    training_data = models.CharField(max_length=255)
    training_date = models.DateTimeField()
    model_summary = models.TextField(blank=True)

    def __str__(self):
        return f"{self.model_name} - {self.training_date.strftime('%Y-%m-%d')}"
    
class ModelAbell(models.Model):
    model_name = models.CharField(max_length=100)
    model_file = models.CharField(max_length=255)
    training_data = models.CharField(max_length=255)
    training_date = models.DateTimeField()
    model_summary = models.TextField(blank=True)

    def __str__(self):
        return f"{self.model_name} - {self.training_date.strftime('%Y-%m-%d')}"
    
class ModelCecil(models.Model):
    model_name = models.CharField(max_length=100)
    model_file = models.CharField(max_length=255)
    training_data = models.CharField(max_length=255)
    training_date = models.DateTimeField()
    model_summary = models.TextField(blank=True)

    def __str__(self):
        return f"{self.model_name} - {self.training_date.strftime('%Y-%m-%d')}"
