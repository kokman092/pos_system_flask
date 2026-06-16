"""Forms package"""
from .auth_forms import LoginForm, ForgotPasswordForm, ResetPasswordForm, ChangePasswordForm
from .menu_forms import CategoryForm, MenuItemForm, ModifierForm
from .order_forms import CreateOrderForm, AddItemForm, PaymentForm, CancelItemForm, ApplyDiscountForm
from .inventory_forms import AddStockBatchForm, WasteLogForm, AdjustStockForm, InventoryCountForm, SubmitCountForm, CountItemForm
from .employee_forms import InviteEmployeeForm, EditEmployeeForm, ChangeRoleForm
from .reservation_forms import ReservationForm, UpdateReservationStatusForm
from .loyalty_forms import FindCustomerForm, CreateCustomerForm
from .settings_forms import PrinterConfigForm, BranchSettingsForm
