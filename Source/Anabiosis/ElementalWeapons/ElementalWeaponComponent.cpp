#include "ElementalWeaponComponent.h"
#include "ElementalFirstPersonCharacter.h"
#include "ElementalWeaponDefinition.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputCoreTypes.h"
#include "Math/RotationMatrix.h"
#include "UObject/ConstructorHelpers.h"

UElementalWeaponComponent::UElementalWeaponComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    StreamShape = Sphere.Object;
}

bool UElementalWeaponComponent::IsReady() const
{
    const AElementalFirstPersonCharacter* Owner = Cast<AElementalFirstPersonCharacter>(GetOwner());
    return Owner && Owner->WeaponLoadout.Num() == 2 && Owner->WeaponLoadout[0] && Owner->WeaponLoadout[1]
        && Owner->WeaponLoadout[0]->Mesh && Owner->WeaponLoadout[1]->Mesh;
}

UElementalWeaponDefinition* UElementalWeaponComponent::Definition() const
{
    return IsReady() ? Cast<AElementalFirstPersonCharacter>(GetOwner())->WeaponLoadout[Frame.WeaponIndex].Get() : nullptr;
}

void UElementalWeaponComponent::BeginPlay()
{
    Super::BeginPlay();
    Character = Cast<AElementalFirstPersonCharacter>(GetOwner());
    if (!IsReady())
    {
        UE_LOG(LogTemp, Warning, TEXT("Elemental weapons: assign both generated weapon definitions to WeaponLoadout."));
        return;
    }
    HipFOV = Character->GetFirstPersonCameraComponent()->FieldOfView;
    WeaponRoot = NewObject<USceneComponent>(Character, TEXT("ElementalWeaponRoot"));
    Character->AddInstanceComponent(WeaponRoot);
    WeaponRoot->SetupAttachment(Character->GetFirstPersonCameraComponent());
    WeaponRoot->RegisterComponent();
    const auto MakeVisual = [this](const FName Name, USceneComponent* Parent)
    {
        UStaticMeshComponent* Mesh = NewObject<UStaticMeshComponent>(Character, Name);
        Character->AddInstanceComponent(Mesh);
        Mesh->SetupAttachment(Parent);
        Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Mesh->SetGenerateOverlapEvents(false);
        Mesh->SetCanEverAffectNavigation(false);
        Mesh->SetOnlyOwnerSee(true);
        Mesh->SetCastShadow(false);
        Mesh->FirstPersonPrimitiveType = EFirstPersonPrimitiveType::FirstPerson;
        Mesh->RegisterComponent();
        return Mesh;
    };
    WeaponMesh = MakeVisual(TEXT("ElementalWeaponMesh"), WeaponRoot);
    // Stream is in world space so traces and visual endpoints agree.
    StreamMesh = MakeVisual(TEXT("ElementalStream"), Character->GetRootComponent());
    StreamMesh->SetStaticMesh(StreamShape);
    StreamMesh->SetVisibility(false);
    ApplyWeapon();
}

void UElementalWeaponComponent::BindInputs(UInputComponent* Input)
{
    ReleaseInput();
    UEnhancedInputComponent* Enhanced = Cast<UEnhancedInputComponent>(Input);
    const APawn* Pawn = Cast<APawn>(GetOwner());
    const APlayerController* PC = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
    ULocalPlayer* Local = PC ? PC->GetLocalPlayer() : nullptr;
    UEnhancedInputLocalPlayerSubsystem* Subsystem = Local ? Local->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
    if (!Enhanced || !Subsystem) return;
    Mapping = NewObject<UInputMappingContext>(this);
    const auto Action = [this](const TCHAR* Name)
    {
        UInputAction* Result = NewObject<UInputAction>(this, MakeUniqueObjectName(this, UInputAction::StaticClass(), Name));
        Result->ValueType = EInputActionValueType::Boolean;
        return Result;
    };
    FireAction = Action(TEXT("ElementalFire"));
    AimAction = Action(TEXT("ElementalAim"));
    FlameAction = Action(TEXT("ElementalSelectFlame"));
    WaterAction = Action(TEXT("ElementalSelectWater"));
    Mapping->MapKey(FireAction, EKeys::LeftMouseButton);
    Mapping->MapKey(AimAction, EKeys::RightMouseButton);
    Mapping->MapKey(FlameAction, EKeys::One);
    Mapping->MapKey(WaterAction, EKeys::Two);
    BindingHandles.Add(Enhanced->BindAction(FireAction, ETriggerEvent::Started, this, &ThisClass::StartFire).GetHandle());
    BindingHandles.Add(Enhanced->BindAction(FireAction, ETriggerEvent::Completed, this, &ThisClass::StopFire).GetHandle());
    BindingHandles.Add(Enhanced->BindAction(FireAction, ETriggerEvent::Canceled, this, &ThisClass::StopFire).GetHandle());
    BindingHandles.Add(Enhanced->BindAction(AimAction, ETriggerEvent::Started, this, &ThisClass::StartAim).GetHandle());
    BindingHandles.Add(Enhanced->BindAction(AimAction, ETriggerEvent::Completed, this, &ThisClass::StopAim).GetHandle());
    BindingHandles.Add(Enhanced->BindAction(AimAction, ETriggerEvent::Canceled, this, &ThisClass::StopAim).GetHandle());
    BindingHandles.Add(Enhanced->BindAction(FlameAction, ETriggerEvent::Started, this, &ThisClass::SelectFlame).GetHandle());
    BindingHandles.Add(Enhanced->BindAction(WaterAction, ETriggerEvent::Started, this, &ThisClass::SelectWater).GetHandle());
    BoundInput = Enhanced;
    InputSubsystem = Subsystem;
    Subsystem->AddMappingContext(Mapping, 10);
}

void UElementalWeaponComponent::ReleaseInput()
{
    if (UEnhancedInputComponent* Input = BoundInput.Get())
        for (uint32 Handle : BindingHandles) Input->RemoveBindingByHandle(Handle);
    if (InputSubsystem.IsValid() && Mapping) InputSubsystem->RemoveMappingContext(Mapping);
    BindingHandles.Empty();
    BoundInput.Reset();
    InputSubsystem.Reset();
    bTrigger = bAiming = bHaveLook = false;
    QueuedWeapon = -1;
    Motion = AnabiosisWeapons::MotionState();
    Frame = AnabiosisWeapons::MotionFrame();
    if (StreamMesh) StreamMesh->SetVisibility(false);
    if (Character && WeaponRoot) ApplyWeapon();
    if (Character)
    {
        Character->GetFirstPersonCameraComponent()->SetFieldOfView(HipFOV);
        Character->GetFirstPersonCameraComponent()->SetFirstPersonFieldOfView(HipFOV);
    }
}

void UElementalWeaponComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    ReleaseInput();
    Super::EndPlay(Reason);
}

void UElementalWeaponComponent::StartFire() { bTrigger = true; }
void UElementalWeaponComponent::StopFire() { bTrigger = false; if (StreamMesh) StreamMesh->SetVisibility(false); }
void UElementalWeaponComponent::StartAim() { bAiming = true; }
void UElementalWeaponComponent::StopAim() { bAiming = false; }
void UElementalWeaponComponent::SelectFlame() { QueuedWeapon = 0; }
void UElementalWeaponComponent::SelectWater() { QueuedWeapon = 1; }

void UElementalWeaponComponent::ApplyWeapon()
{
    const UElementalWeaponDefinition* Def = Definition();
    if (!Def || !WeaponMesh) return;
    WeaponMesh->SetStaticMesh(Def->Mesh);
    WeaponMesh->SetRelativeTransform(FTransform(Def->MeshRotation, Def->MeshTranslation, FVector(Def->MeshScale)));
    StreamMesh->SetMaterial(0, Def->StreamMaterial);
    StreamMesh->SetVisibility(false);
    if (UAnimInstance* Anim = Character->GetFirstPersonMesh()->GetAnimInstance()) Anim->Montage_Stop(.06f);
}

void UElementalWeaponComponent::TickComponent(float Dt, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(Dt, TickType, TickFunction);
    if (!WeaponRoot || !Character || !Character->IsLocallyControlled())
    {
        if (StreamMesh) StreamMesh->SetVisibility(false);
        return;
    }
    AnabiosisWeapons::MotionInput Input;
    Input.DeltaSeconds = Dt;
    Input.Speed = Character->GetVelocity().Size2D();
    Input.Aiming = bAiming;
    Input.Trigger = bTrigger;
    Input.SelectWeapon = QueuedWeapon;
    QueuedWeapon = -1;
    const FRotator Look = Character->GetControlRotation();
    Character->GetFirstPersonCameraComponent()->SetWorldRotation(Look);
    const FRotator Change = (Look - PreviousLook).GetNormalized();
    if (bHaveLook && Dt > SMALL_NUMBER)
    {
        Input.TurnYawRate = Change.Yaw / Dt;
        Input.TurnPitchRate = Change.Pitch / Dt;
    }
    bHaveLook = true;
    PreviousLook = Look;
    Frame = Motion.Update(Input);
    if (Frame.WeaponChanged) ApplyWeapon();
    const UElementalWeaponDefinition* Def = Definition();
    if (!Def) return;
    const float Aim = static_cast<float>(Frame.AimAlpha);
    FVector Position = FMath::Lerp(Def->HipLocation, Def->AimLocation, Aim);
    Position += FVector(-Frame.RecoilBack * Def->RecoilScale, Frame.WalkSide, Frame.WalkUp - Frame.SwitchDrop * 32);
    const FQuat BaseRotation = FQuat::Slerp(Def->HipRotation.Quaternion(), Def->AimRotation.Quaternion(), Aim);
    const FRotator MotionRotation(Frame.RecoilPitch * Def->RecoilScale + Frame.SwayPitch * Def->SwayScale,
                                 Frame.SwayYaw * Def->SwayScale, Frame.Roll);
    WeaponRoot->SetRelativeLocationAndRotation(Position, (BaseRotation * MotionRotation.Quaternion()).GetNormalized());
    const float FOV = FMath::Lerp(HipFOV, Def->AimFOV, Aim);
    Character->GetFirstPersonCameraComponent()->SetFieldOfView(FOV);
    Character->GetFirstPersonCameraComponent()->SetFirstPersonFieldOfView(FOV);
    if (Frame.Switching)
    {
        if (UAnimInstance* Anim = Character->GetFirstPersonMesh()->GetAnimInstance()) Anim->Montage_Stop(.04f);
    }
    else if (Frame.FirePulse && Def->AttackPose)
    {
        if (UAnimInstance* Anim = Character->GetFirstPersonMesh()->GetAnimInstance())
            Anim->PlaySlotAnimationAsDynamicMontage(Def->AttackPose, TEXT("DefaultSlot"), .035f, .08f,
                                                   Frame.WeaponIndex == 1 ? 1.8f : 1.f);
    }
    UpdateStream();
}

void UElementalWeaponComponent::UpdateStream()
{
    const UElementalWeaponDefinition* Def = Definition();
    StreamMesh->SetVisibility(Frame.Attacking && bTrigger && Def && Def->StreamMaterial);
    if (!Frame.Attacking || !Def) return;
    const UCameraComponent* Camera = Character->GetFirstPersonCameraComponent();
    const FVector Start = WeaponRoot->GetComponentTransform().TransformPosition(Def->MuzzleOffset);
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ElementalVisualStream), true, Character);
    FHitResult Hit;
    const FVector ViewStart = Camera->GetComponentLocation();
    // A long barrel can project past a nearby wall. Suppress the stream rather
    // than drawing it back through the weapon or starting beyond the wall.
    if (GetWorld()->LineTraceSingleByChannel(Hit, ViewStart, Start, ECC_Visibility, Params))
    {
        StreamMesh->SetVisibility(false);
        return;
    }
    FVector Target = ViewStart + Camera->GetForwardVector() * (Def->StreamRange + 100);
    if (GetWorld()->LineTraceSingleByChannel(Hit, ViewStart, Target, ECC_Visibility, Params)) Target = Hit.ImpactPoint;
    FVector Direction = (Target - Start).GetSafeNormal();
    const float DesiredLength = FMath::Min(static_cast<float>((Target-Start).Size()), Def->StreamRange);
    FVector End = Start + Direction * DesiredLength;
    if (GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params)) End = Hit.ImpactPoint;
    const float Length = static_cast<float>((End-Start).Size());
    Direction = (End-Start).GetSafeNormal();
    const float Width = Def->StreamWidth * (Frame.WeaponIndex == 0 ? 1.f + .08f * FMath::Sin(GetWorld()->GetTimeSeconds()*37) : 1.f);
    StreamMesh->SetWorldTransform(FTransform(FRotationMatrix::MakeFromZ(Direction).ToQuat(),
        (Start+End)*.5, FVector(Width/100, Width/100, FMath::Max(Length, .1f)/100)));
}

FElementalArmTargets UElementalWeaponComponent::GetArmTargets() const
{
    FElementalArmTargets Result;
    const UElementalWeaponDefinition* Def = Definition();
    if (!Def || !WeaponRoot || !Character) return Result;
    const FTransform Mesh = Character->GetFirstPersonMesh()->GetComponentTransform();
    const FTransform Weapon = WeaponRoot->GetComponentTransform();
    const FTransform View = Character->GetFirstPersonCameraComponent()->GetComponentTransform();
    Result.Pose = Def->HoldPose;
    Result.RightHand = Mesh.InverseTransformPosition(Weapon.TransformPosition(Def->RightHandOffset));
    Result.LeftHand = Mesh.InverseTransformPosition(Weapon.TransformPosition(Def->LeftHandOffset));
    Result.RightElbow = Mesh.InverseTransformPosition(View.TransformPosition(Def->RightElbowOffset));
    Result.LeftElbow = Mesh.InverseTransformPosition(View.TransformPosition(Def->LeftElbowOffset));
    const FQuat NeutralView = FRotator(0, Character->GetActorRotation().Yaw, 0).Quaternion();
    const FQuat DeltaWorld = Weapon.GetRotation() * NeutralView.Inverse();
    Result.WristRotation = (Mesh.GetRotation().Inverse() * DeltaWorld * Mesh.GetRotation()).Rotator();
    Result.Valid = Result.Pose != nullptr;
    return Result;
}
