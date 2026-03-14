<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { RouterLink } from 'vue-router'

const authStore = useAuthStore()
const isAuthenticated = computed(() => authStore.isAuthenticated())
</script>

<template>
  <div class="public-page">
    <div class="public-container">
      <div class="text-center mb-lg">
        <h1>Underway</h1>
        <p class="lead">Spend your time on what matters to you.</p>
      </div>

      <p class="intro">You know how you want to spend your time — health, relationships, meaningful work. But somehow the day fills up with other things. Underway fixes that.</p>

      <h3>What should I do next?</h3>
      <p>That's the question Underway answers. You tell it your priorities, and it helps you manage your time accordingly — organising tasks and scheduling focused work blocks around your existing commitments.</p>

      <h3>Tell it what matters</h3>
      <p>You can set two kinds of goals:</p>
      <ul>
        <li><strong>Time goals</strong> — "I want to spend 8 hours a week on fitness"</li>
        <li><strong>Recurring goals</strong> — "Call Joe every 30 days"</li>
      </ul>
      <p>Underway tracks your progress against these goals and helps you stay on track.</p>

      <h3>It decides what comes first</h3>
      <p>Underway doesn't just shuffle tasks randomly. It prioritises based on what matters most right now: hard deadlines come first, then goals where you're falling behind, then things you haven't done in a while. It also tries to keep you in flow by grouping similar work together.</p>

      <h3>It adapts to reality</h3>
      <p>Plans change. Something urgent comes up, or a task takes longer than expected. Traditional planners just mark everything overdue. Underway reschedules around what actually happened, so your plan always reflects today, not last Monday.</p>

      <h3>It asks when it's unsure</h3>
      <p>If Underway can't figure out the next step for a goal, it'll ask rather than guess. For example: <em>"Your top priority is marathon training, but I'm not sure what to schedule. Should I put in a run, or would you rather plan a training programme first?"</em></p>

      <h3>Your calendar stays yours</h3>
      <p>Underway writes to a dedicated calendar and never touches your existing events. You'll always see its suggestions as separate blocks alongside your normal schedule.</p>

      <h3>Simple to use</h3>
      <p>Tell Underway what matters to you. Check your calendar to see what to work on next. Let it know when things change. That's it.</p>

      <h3>Pricing</h3>
      <p>Underway is currently free. No credit card needed. If that changes, we'll let you know well in advance.</p>

      <div class="text-center mt-lg">
        <RouterLink v-if="isAuthenticated" to="/chat" class="btn btn-primary" data-automation-id="about-cta-button">Go to Chat</RouterLink>
        <RouterLink v-else to="/login" class="btn btn-primary" data-automation-id="about-cta-button">Get Started</RouterLink>
      </div>

      <div class="text-center mt-sm">
        <RouterLink to="/login" class="back-link" data-automation-id="about-back-link">&larr; Back to Login</RouterLink>
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

.mb-lg {
  margin-bottom: 2.5rem;
}

.mt-lg {
  margin-top: 2.5rem;
}

.mt-sm {
  margin-top: 1rem;
}

h1 {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.lead {
  font-size: 1.15rem;
  color: var(--color-text-muted, #888);
}

.intro {
  font-size: 1.05rem;
  margin-bottom: 2rem;
}

h3 {
  margin-top: 2rem;
  margin-bottom: 0.5rem;
}

ul {
  padding-left: 1.5rem;
}

.btn {
  display: inline-block;
  padding: 0.75rem 2rem;
  border-radius: 8px;
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
}

.btn-primary {
  background: var(--color-primary, #4a90d9);
  color: #fff;
}

.btn-primary:hover {
  opacity: 0.9;
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
