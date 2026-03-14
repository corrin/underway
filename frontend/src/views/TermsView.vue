<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="public-page">
    <div class="public-container">
      <h1>Terms of Service</h1>
      <p>Welcome to Underway. By accessing or using our service, you agree to be bound by the following terms and conditions:</p>

      <ol>
        <li>Your use of the application must comply with all applicable laws and regulations.</li>
        <li>You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.</li>
        <li>We reserve the right to modify or discontinue the application at any time without notice.</li>
        <li>We are not liable for any damages or losses arising from your use of the application.</li>
        <li>These terms and conditions are governed by the laws of New Zealand. Any disputes arising from your use of the application will be subject to the exclusive jurisdiction of the courts in New Zealand.</li>
      </ol>

      <p>If you have any questions about these terms and conditions, please contact us at <a href="mailto:lakeland@gmail.com">lakeland@gmail.com</a>.</p>

      <div class="text-center mt-lg">
        <RouterLink to="/login" class="back-link" data-automation-id="terms-back-link">&larr; Back to Login</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.public-page {
  display: flex;
  justify-content: center;
  min-height: 100vh;
  padding: 3rem 1.5rem;
}

.public-container {
  max-width: 640px;
  width: 100%;
}

.text-center {
  text-align: center;
}

.mt-lg {
  margin-top: 2.5rem;
}

h1 {
  font-size: 2rem;
  margin-bottom: 1.5rem;
}

ol {
  padding-left: 1.5rem;
}

ol li {
  margin-bottom: 0.75rem;
}

.back-link {
  color: var(--color-text-muted, #888);
  text-decoration: none;
  font-size: 0.9rem;
}

.back-link:hover {
  text-decoration: underline;
}
</style>
