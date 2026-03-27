import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { Modal } from './Modal';

describe('Modal', () => {
  afterEach(cleanup);

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <Modal isOpen={false} onClose={() => {}} title="Test">
        Content
      </Modal>
    );
    expect(container.querySelector('.modal-overlay')).toBeNull();
  });

  it('renders the modal when isOpen is true', () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="My Title">
        Hello
      </Modal>
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('My Title')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="Accessible">
        Body
      </Modal>
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby');

    const titleId = dialog.getAttribute('aria-labelledby')!;
    const titleEl = document.getElementById(titleId);
    expect(titleEl).not.toBeNull();
    expect(titleEl!.textContent).toBe('Accessible');
  });

  it('calls onClose when Escape key is pressed', () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="Esc Test">
        Content
      </Modal>
    );
    fireEvent.keyDown(screen.getByRole('dialog').parentElement!, {
      key: 'Escape',
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when overlay is clicked', () => {
    const onClose = vi.fn();
    const { container } = render(
      <Modal isOpen={true} onClose={onClose} title="Overlay Test">
        Content
      </Modal>
    );
    const overlay = container.querySelector('.modal-overlay')!;
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not call onClose when modal content is clicked', () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="Content Click">
        <p>Inner</p>
      </Modal>
    );
    fireEvent.click(screen.getByText('Inner'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="Close Btn">
        Content
      </Modal>
    );
    fireEvent.click(screen.getByLabelText('Close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders footer when provided', () => {
    render(
      <Modal
        isOpen={true}
        onClose={() => {}}
        title="Footer"
        footer={<button>Save</button>}
      >
        Content
      </Modal>
    );
    expect(screen.getByText('Save')).toBeInTheDocument();
  });

  it('does not render footer when not provided', () => {
    const { container } = render(
      <Modal isOpen={true} onClose={() => {}} title="No Footer">
        Content
      </Modal>
    );
    expect(container.querySelector('.modal__footer')).toBeNull();
  });

  it.each(['sm', 'md', 'lg'] as const)('applies size class modal--%s', (size) => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="Size" size={size}>
        Content
      </Modal>
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog.classList.contains(`modal--${size}`)).toBe(true);
  });

  it('defaults to md size', () => {
    render(
      <Modal isOpen={true} onClose={() => {}} title="Default">
        Content
      </Modal>
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog.classList.contains('modal--md')).toBe(true);
  });

  it('traps focus within the modal (Tab on last element wraps to first)', () => {
    render(
      <Modal
        isOpen={true}
        onClose={() => {}}
        title="Focus Trap"
        footer={<button>Action</button>}
      >
        <input data-testid="input1" />
      </Modal>
    );

    const closeBtn = screen.getByLabelText('Close');
    screen.getByTestId('input1');
    const actionBtn = screen.getByText('Action');

    // Focus the last focusable element
    actionBtn.focus();
    expect(document.activeElement).toBe(actionBtn);

    // Tab should wrap to the first focusable element (close button)
    fireEvent.keyDown(screen.getByRole('dialog').parentElement!, {
      key: 'Tab',
    });
    expect(document.activeElement).toBe(closeBtn);
  });

  it('traps focus within the modal (Shift+Tab on first element wraps to last)', () => {
    render(
      <Modal
        isOpen={true}
        onClose={() => {}}
        title="Focus Trap Reverse"
        footer={<button>Action</button>}
      >
        <input data-testid="input1" />
      </Modal>
    );

    const closeBtn = screen.getByLabelText('Close');
    const actionBtn = screen.getByText('Action');

    // Focus the first focusable element (close button)
    closeBtn.focus();
    expect(document.activeElement).toBe(closeBtn);

    // Shift+Tab should wrap to the last focusable element
    fireEvent.keyDown(screen.getByRole('dialog').parentElement!, {
      key: 'Tab',
      shiftKey: true,
    });
    expect(document.activeElement).toBe(actionBtn);
  });
});
