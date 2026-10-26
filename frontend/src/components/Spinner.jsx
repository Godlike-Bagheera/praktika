export default function Spinner({ text = 'Загрузка...' }) {
  return (
    <div className="d-flex justify-content-center my-5">
      <div className="spinner-border text-primary" role="status">
        <span className="visually-hidden">{text}</span>
      </div>
    </div>
  );
}
