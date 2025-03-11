from rest_framework import serializers
from accounts.models import CustomUser
from accounts.utils import verify_recaptcha

class RegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    g_recaptcha_response = serializers.CharField(write_only=True)
    
    class Meta:
        model = CustomUser
        fields = ["username", "email", "password1", "password2", "gender", "city", "age", "g_recaptcha_response"]

    def validate(self, data):
        # ✅ Ensure passwords match
        if data["password1"] != data["password2"]:
            raise serializers.ValidationError({"password2": "Passwords do not match."})

        # ✅ Validate reCAPTCHA using `accounts/utils.py`
        is_valid, recaptcha_error = verify_recaptcha(data.get("g_recaptcha_response"))
        if not is_valid:
            raise serializers.ValidationError({"recaptcha": f"reCAPTCHA failed: {recaptcha_error}"})

        return data

    def create(self, validated_data):
        # ✅ Remove unnecessary fields
        validated_data.pop("password1")
        validated_data.pop("password2")
        validated_data.pop("g_recaptcha_response")

        # ✅ Hash the password before saving
        password = self.initial_data.get("password1")
        user = CustomUser(**validated_data)
        user.set_password(password)  # Hash the password
        user.save()
        return user
