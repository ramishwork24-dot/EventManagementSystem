from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse


#mock templates so that tests don't need physical template files
TEST_AUTH_TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': False,
    'OPTIONS': {
        'loaders': [
            ('django.template.loaders.locmem.Loader', {
                'accounts/signup.html': '{% block content %}{% endblock %}',
                'accounts/login.html': '{% block content %}{% endblock %}',
                'event/event_home.html': '{% block content %}{% endblock %}',
                'event/event_detail.html': '{% block content %}{% endblock %}',
            }),
        ],
    },
}]

@override_settings(TEMPLATES=TEST_AUTH_TEMPLATES)
class AuthViewTest(TestCase):
    def test_signup_view_get_and_successful_post(self):
        #GET request retrieves sign up page
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)

        #POST valid user authentication data
        post_data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'ComplexPassword123!',
            'password2': 'ComplexPassword123!',
        }
        response = self.client.post(reverse('signup'), post_data)

        #verify successful registration and redirect to login page
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_login_logout_flow(self):
        User.objects.create_user('testuser', 'user@test.com', 'Password123')

        #falied login with wrong password
        response = self.client.post(reverse('login'), {'username': 'testuser', 'password': 'passwordwrong'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

        # successful login
        response = self.client.post(reverse('login'), {'username': 'testuser', 'password': 'Password123'})
        self.assertRedirects(response, reverse('event_home'))
        self.assertIn('_auth_user_id', self.client.session)

        #Logout clears session
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('event_home'))
        self.assertNotIn('_auth_user_id', self.client.session)
