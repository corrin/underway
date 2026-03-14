import api from '@/api/client'

export async function initiateTodoistOAuth(): Promise<{ authorization_url: string }> {
  const response = await api.post('/oauth/todoist/initiate')
  return response.data
}
