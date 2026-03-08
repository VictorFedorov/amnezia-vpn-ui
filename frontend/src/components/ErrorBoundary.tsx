import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Если задан, показывается вместо дефолтного UI */
  fallback?: ReactNode;
  /** Контекст для отображения в сообщении об ошибке (например, название страницы) */
  context?: string;
}

interface State {
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', this.props.context ?? 'unknown', error, info.componentStack);
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) return this.props.fallback;

    const { context } = this.props;

    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-lg w-full">
          <h2 className="text-lg font-semibold text-red-800 mb-2">
            {context ? `Ошибка в "${context}"` : 'Что-то пошло не так'}
          </h2>
          <p className="text-sm text-red-600 mb-4 font-mono break-all">
            {error.message}
          </p>
          <button
            onClick={this.reset}
            className="px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
          >
            Попробовать снова
          </button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
