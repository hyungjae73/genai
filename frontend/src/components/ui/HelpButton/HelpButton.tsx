import { useState, type ReactNode } from 'react';
import { Modal } from '../Modal/Modal';
import './HelpButton.css';

export interface HelpButtonProps {
  title: string;
  children: ReactNode;
}

export const HelpButton: React.FC<HelpButtonProps> = ({ title, children }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        className="help-button"
        type="button"
        aria-label="ヘルプを表示"
        onClick={() => setIsOpen(true)}
      >
        ?
      </button>
      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title={title} size="md">
        {children}
      </Modal>
    </>
  );
};

export default HelpButton;
