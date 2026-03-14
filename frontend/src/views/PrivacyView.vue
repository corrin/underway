<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="public-page">
    <div class="public-container">
      <h1>Privacy Statement</h1>
      <p>At Underway, we are committed to protecting your privacy. This privacy statement explains how we collect, use, and disclose your personal information.</p>

      <h2>Information We Collect</h2>
      <p>We may collect the following information when you use our application:</p>
      <ul>
        <li>Your name and email address when you register for an account.</li>
        <li>Your calendar data, including event titles, start and end times, and attendees, when you sync your calendars.</li>
        <li>Your task data when you connect task management services.</li>
        <li>Usage data, such as your IP address and browser type, to analyse trends and improve our application.</li>
      </ul>

      <h2>How We Use Your Information</h2>
      <p>We use your information to provide and improve our task and calendar management service, to communicate with you about your account, and to personalise your experience.</p>

      <h2>Information Sharing and Disclosure</h2>
      <p>We do not sell, trade, or otherwise transfer your personal information to third parties unless we have your consent or are required to do so by law.</p>

      <h2>Data Security</h2>
      <p>We implement reasonable security measures to protect your information from unauthorised access, alteration, or destruction.</p>

      <h2>Changes to This Privacy Statement</h2>
      <p>We may update this privacy statement from time to time. We will notify you of any changes by posting the new privacy statement on this page.</p>

      <p>If you have any questions about this privacy statement, please contact us at <a href="mailto:lakeland@gmail.com">lakeland@gmail.com</a>.</p>

      <div class="text-center mt-lg">
        <RouterLink to="/login" class="back-link" data-automation-id="privacy-back-link">&larr; Back to Login</RouterLink>
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

h2 {
  margin-top: 2rem;
  margin-bottom: 0.5rem;
  font-size: 1.3rem;
}

ul {
  padding-left: 1.5rem;
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
