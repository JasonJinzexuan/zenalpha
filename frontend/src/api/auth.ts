import http from './http'
import type { ApiResponse, LoginRequest, LoginResponse, RegisterRequest } from '@/types/api'

export async function login(req: LoginRequest): Promise<LoginResponse> {
  const { data } = await http.post<ApiResponse<LoginResponse>>('/users/login', req)
  if (!data.success || !data.data) throw new Error(data.error || 'Login failed')
  return data.data
}

export async function register(req: RegisterRequest): Promise<string> {
  const { data } = await http.post<ApiResponse<string>>('/users/register', req)
  if (!data.success) throw new Error(data.error || 'Registration failed')
  return data.data || 'OK'
}
