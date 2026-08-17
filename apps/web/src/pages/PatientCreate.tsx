import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createPatient, type PatientCreateInput } from '../api/patients'

interface FormState {
  legalName: string
  preferredName: string
  dateOfBirth: string
  email: string
  phone: string
  preferredLanguage: string
}

const initialState: FormState = {
  legalName: '',
  preferredName: '',
  dateOfBirth: '',
  email: '',
  phone: '',
  preferredLanguage: 'en',
}

type FormErrors = Partial<Record<keyof FormState, string>>

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {}
  if (!form.legalName.trim()) {
    errors.legalName = 'Legal name is required.'
  }
  if (!form.dateOfBirth) {
    errors.dateOfBirth = 'Date of birth is required.'
  }
  if (form.email.trim() && !EMAIL_PATTERN.test(form.email.trim())) {
    errors.email = 'Enter a valid email address.'
  }
  if (!form.email.trim() && !form.phone.trim()) {
    errors.phone = 'Provide an email or a phone number.'
  }
  return errors
}

export function PatientCreate() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState>(initialState)
  const [errors, setErrors] = useState<FormErrors>({})

  const mutation = useMutation({
    mutationFn: (request: PatientCreateInput) => createPatient(request),
    onSuccess: (patient) => navigate(`/patients/${patient.patientId}`),
  })

  function update<K extends keyof FormState>(key: K, value: string) {
    setForm((previous) => ({ ...previous, [key]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const validationErrors = validate(form)
    setErrors(validationErrors)
    if (Object.keys(validationErrors).length > 0) {
      return
    }

    const request: PatientCreateInput = {
      patientId: crypto.randomUUID(),
      legalName: form.legalName.trim(),
      preferredName: form.preferredName.trim() || undefined,
      dateOfBirth: form.dateOfBirth,
      contact: {
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
      },
      preferredLanguage: form.preferredLanguage.trim() || 'en',
    }
    mutation.mutate(request)
  }

  return (
    <section>
      <h1>New patient</h1>
      <form onSubmit={handleSubmit} noValidate>
        <label>
          Legal name
          <input value={form.legalName} onChange={(event) => update('legalName', event.target.value)} />
        </label>
        {errors.legalName && <p role="alert">{errors.legalName}</p>}

        <label>
          Preferred name
          <input value={form.preferredName} onChange={(event) => update('preferredName', event.target.value)} />
        </label>

        <label>
          Date of birth
          <input
            type="date"
            value={form.dateOfBirth}
            onChange={(event) => update('dateOfBirth', event.target.value)}
          />
        </label>
        {errors.dateOfBirth && <p role="alert">{errors.dateOfBirth}</p>}

        <label>
          Email
          <input type="email" value={form.email} onChange={(event) => update('email', event.target.value)} />
        </label>
        {errors.email && <p role="alert">{errors.email}</p>}

        <label>
          Phone
          <input value={form.phone} onChange={(event) => update('phone', event.target.value)} />
        </label>
        {errors.phone && <p role="alert">{errors.phone}</p>}

        <label>
          Preferred language
          <input
            value={form.preferredLanguage}
            onChange={(event) => update('preferredLanguage', event.target.value)}
          />
        </label>

        {mutation.isError && (
          <p role="alert">
            {mutation.error instanceof Error ? mutation.error.message : 'Failed to create patient.'}
          </p>
        )}

        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Creating…' : 'Create patient'}
        </button>
      </form>
    </section>
  )
}
