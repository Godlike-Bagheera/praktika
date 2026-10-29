import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal } from 'bootstrap';
import { api, errorMessage } from '../api';

const REASONS = [
  { value: 'spam', label: 'Спам' },
  { value: 'offtopic', label: 'Не по теме' },
  { value: 'insult', label: 'Оскорбление' },
  { value: 'other', label: 'Другое' },
];

// Кнопка «Пожаловаться» с Bootstrap-модалкой выбора причины.
// Не рендерится для собственных постов пользователя.
export default function ReportButton({ postId, isOwnPost }) {
  const modalRef = useRef(null);
  const modalInstance = useRef(null);
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false); // жалоба уже отправлена — дизейблим кнопку
  const [notice, setNotice] = useState(''); // сообщение об успехе/ошибке внутри модалки
  const navigate = useNavigate();

  // Инициализация модалки Bootstrap (без сторонних библиотек)
  useEffect(() => {
    if (modalRef.current && !modalInstance.current) {
      modalInstance.current = new Modal(modalRef.current, { backdrop: true });
    }
    return () => {
      modalInstance.current?.dispose();
      modalInstance.current = null;
    };
  }, []);

  if (isOwnPost) return null;

  const openModal = () => {
    setNotice('');
    modalInstance.current?.show();
  };

  const closeModal = () => {
    modalInstance.current?.hide();
  };

  const submitReason = async (reason) => {
    if (sending) return;
    setSending(true);
    setNotice('');
    try {
      await api.post(`/posts/${postId}/report/`, { post: postId, reason });
      closeModal();
      setDone(true);
      window.alert('Жалоба отправлена');
    } catch (err) {
      const msg = errorMessage(err) || '';
      if (/уже жаловались/i.test(msg)) {
        setNotice('Вы уже отправляли жалобу на это сообщение');
        setDone(true); // повторная жалоба невозможна — кнопку больше не активим
      } else if (err?.response?.status === 401) {
        closeModal();
        navigate('/login');
      } else {
        setNotice(msg || 'Не удалось отправить жалобу, попробуйте позже');
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className={`btn btn-sm px-2 ${done ? 'btn-secondary disabled' : 'btn-outline-secondary'}`}
        onClick={openModal}
        disabled={done}
        title={done ? 'Жалоба уже отправлена' : 'Пожаловаться на сообщение'}
      >
        🚩 {done ? 'Жалоба отправлена' : 'Пожаловаться'}
      </button>

      <div
        ref={modalRef}
        className="modal fade"
        tabIndex={-1}
        aria-hidden="true"
        role="dialog"
      >
        <div className="modal-dialog modal-dialog-centered">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">Пожаловаться на сообщение</h5>
              <button
                type="button"
                className="btn-close"
                aria-label="Закрыть"
                onClick={closeModal}
              />
            </div>
            <div className="modal-body d-grid gap-2">
              {notice && (
                <div className="alert alert-warning py-2 mb-2" role="alert">
                  {notice}
                </div>
              )}
              {REASONS.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  className="btn btn-outline-primary text-start"
                  disabled={sending}
                  onClick={() => submitReason(r.value)}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={closeModal}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
