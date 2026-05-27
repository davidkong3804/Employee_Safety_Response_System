import React, { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6 text-center animate-fade-in">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full shadow-xl border border-gray-100">
            <div className="w-16 h-16 bg-red-50 text-red-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-gray-950 mb-2">Oops! Something went wrong</h1>
            <p className="text-sm text-gray-500 mb-6 leading-relaxed">
              An unexpected error occurred in the application. Please try reloading the page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="w-full py-3 bg-blue-900 hover:bg-blue-800 text-white font-semibold rounded-xl shadow transition"
            >
              Reload Page
            </button>
            {this.state.error && (
              <pre className="mt-6 p-4 bg-gray-50 rounded-xl text-xs text-left text-red-600 overflow-auto max-h-40 border border-gray-100 font-mono">
                {this.state.error.toString()}
              </pre>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
