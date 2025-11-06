'use client'

import RegisterForm from '@/components/auth/RegisterForm'
import { useRouter } from 'next/navigation'

export default function RegisterPage() {
  const router = useRouter()
  return <RegisterForm onSuccess={() => router.push('/login')} />
}
